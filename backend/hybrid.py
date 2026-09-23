"""Elasticsearch Nori/BM25 + Chroma semantic vectors with reproducible fusion.
No lexical substitute is silently used when either service is unavailable.
"""
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path

import httpx


class RetrievalUnavailable(RuntimeError):
    pass


def embeddings():
    from langchain_openai import OpenAIEmbeddings
    if not os.getenv('OPENAI_API_KEY'):
        raise RetrievalUnavailable('OPENAI_API_KEY is required for semantic retrieval')
    return OpenAIEmbeddings(model=os.getenv('EMBEDDING_MODEL','text-embedding-3-small'), max_retries=2, request_timeout=60)


def chroma_client():
    import chromadb
    return chromadb.HttpClient(host=os.getenv('CHROMA_HOST','127.0.0.1'), port=int(os.getenv('CHROMA_PORT','8001')))


def es_request(method, path, **kwargs):
    with httpx.Client(base_url=os.getenv('ELASTIC_URL','http://127.0.0.1:9200'), timeout=60) as client:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()


def bm25_query(query, limit=30):
    return {'size':limit, 'query':{'multi_match':{'query':query,'fields':['title^2','locator^3','text'], 'type':'best_fields'}}}


def fuse(lexical, semantic, query, variant='rrf', k=60):
    if variant not in {'bm25','dense','rrf','adaptive','adaptive-diverse'}:
        raise ValueError('Unknown fusion variant')
    exact = bool(re.search(r'제\s*\d+\s*조|\d{4}\s*[가-힣]{1,4}\s*\d+',query))
    wl, wd = ((2.,1.) if exact else (1.,2.)) if variant.startswith('adaptive') else (1.,1.)
    if variant == 'bm25': wd=0.
    if variant == 'dense': wl=0.
    result = {}
    for channel, entries, weight in [('bm25',lexical,wl),('dense',semantic,wd)]:
        if not weight: continue
        for rank, ident in enumerate(dict.fromkeys(entries),1):
            entry=result.setdefault(ident,{'score':0.,'channels':[],'ranks':{},'weights':{'bm25':wl,'dense':wd}})
            entry['score'] += weight/(k+rank)
            entry['channels'].append(channel)
            entry['ranks'][channel]=rank
    return sorted(result.items(), key=lambda pair:(-pair[1]['score'],pair[0]))


class HybridRetriever:
    def __init__(self, pointer=None, embedder=None, collection=None, request=None):
        self.config=json.loads(Path(pointer or os.getenv('INDEX_POINTER','runtime/active-index.json')).read_text())
        if self.config['embedding_model'] != os.getenv('EMBEDDING_MODEL','text-embedding-3-small'):
            raise RetrievalUnavailable('Embedding model differs from indexed model; rebuild first')
        self.embedder=embedder or embeddings()
        self.collection=collection or chroma_client().get_collection(self.config['name'],embedding_function=None)
        self.request=request or es_request
        self.variant=os.getenv('FUSION_VARIANT','rrf')
        if self.collection.count() != self.config['count']:
            raise RetrievalUnavailable('Chroma corpus is incomplete')
        if self.request('GET',f"/{self.config['name']}/_count")['count'] != self.config['count']:
            raise RetrievalUnavailable('Elasticsearch corpus is incomplete')

    def search(self, query, variant=None):
        variant=variant or self.variant
        name=self.config['name']
        try:
            hits=self.request('POST',f'/{name}/_search',json=bm25_query(query))['hits']['hits']
            # Ignore zero-score lexical matches; semantic distance threshold is an experiment parameter.
            lexical=[h['_id'] for h in hits if h['_score']>0]
            vector=self.embedder.embed_query(query)
            dense=self.collection.query(query_embeddings=[vector],n_results=min(30,self.config['count']),include=['distances'])
            semantic=[ident for ident,dist in zip(dense['ids'][0],dense['distances'][0]) if dist <= float(os.getenv('MAX_COSINE_DISTANCE','0.55'))]
            ranking=fuse(lexical,semantic,query,variant)
            if not ranking:return []
            bodies=self.request('POST',f'/{name}/_mget',json={'ids':[i for i,_ in ranking]})['docs']
            docs={d['_id']:d['_source']['payload'] for d in bodies if d.get('found')}
            if len(docs)!=len(ranking):
                raise RetrievalUnavailable('Cross-store ID mismatch')
            output, parents=[],set()
            for ident, trace in ranking:
                doc=docs[ident]
                # Experimental consensus gate: require both retrievers, not merely one high rank.
                if variant=='adaptive-diverse' and len(trace['channels'])<2:continue
                parent=doc.get('parent_id',ident)
                if variant=='adaptive-diverse' and parent in parents:continue
                parents.add(parent)
                output.append(dict(doc,score=trace['score'],retrieval_trace=trace))
                if len(output)==3:break
            return output
        except RetrievalUnavailable:
            raise
        except Exception as exc:
            raise RetrievalUnavailable('Hybrid service/model failure; no silent demo fallback') from exc


def read_corpus(paths):
    for path in paths:
        with Path(path).open(encoding='utf-8') as stream:
            for line in stream:
                if line.strip():yield json.loads(line)


def build_index(paths, pointer):
    from backend.app import Document
    model=os.getenv('EMBEDDING_MODEL','text-embedding-3-small')
    hashes=[]
    for path in paths:
        h=hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        hashes.append(h.hexdigest())
    fingerprint=hashlib.sha256(json.dumps({'files':hashes,'model':model,'schema':2},sort_keys=True).encode()).hexdigest()
    name='legal-'+fingerprint[:20]
    client=chroma_client()
    collection=client.get_or_create_collection(name,embedding_function=None,configuration={'hnsw':{'space':'cosine'}},metadata={'fingerprint':fingerprint,'embedding_model':model})
    if collection.metadata.get('fingerprint')!=fingerprint:
        raise ValueError('Collection fingerprint mismatch')
    try:
        es_request('PUT','/'+name,json={'settings':{'analysis':{'analyzer':{'legal_ko':{'type':'custom','tokenizer':'nori_tokenizer','filter':['lowercase']}}}},'mappings':{'properties':{'title':{'type':'text','analyzer':'legal_ko'},'locator':{'type':'text','analyzer':'legal_ko'},'text':{'type':'text','analyzer':'legal_ko'},'payload':{'type':'object','enabled':False}}}})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code!=400 or 'resource_already_exists_exception' not in exc.response.text:raise
    embedder=embeddings()
    # SQLite dedup validation scales without retaining all raw documents in memory.
    import sqlite3
    import tempfile
    pointer=Path(pointer)
    pointer.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=pointer.parent) as tmp:
        with sqlite3.connect(Path(tmp)/'ids.sqlite') as ledger:
            ledger.execute('CREATE TABLE ids(id TEXT PRIMARY KEY)')
            batch=[]
            count=0
            def flush(items):
                vectors=embedder.embed_documents([d['title']+'\n'+d['locator']+'\n'+d['text'] for d in items])
                collection.upsert(ids=[d['id'] for d in items],embeddings=vectors,metadatas=[{'parent_id':d.get('parent_id',d['id'])} for d in items])
                body=''.join(json.dumps({'index':{'_index':name,'_id':d['id']}})+'\n'+json.dumps({'title':d['title'],'locator':d['locator'],'text':d['text'],'payload':d},ensure_ascii=False)+'\n' for d in items)
                response=es_request('POST','/_bulk',content=body.encode(),headers={'Content-Type':'application/x-ndjson'})
                if response.get('errors'):raise RetrievalUnavailable('Elasticsearch bulk failed; active pointer unchanged')
            for doc in read_corpus(paths):
                Document.model_validate(doc)
                if doc['kind']=='demo':raise ValueError('Do not index demo as legal evidence')
                try:ledger.execute('INSERT INTO ids VALUES(?)',(doc['id'],))
                except sqlite3.IntegrityError:raise ValueError('Duplicate chunk ID across input files') from None
                batch.append(doc);count+=1
                if len(batch)==32:flush(batch);batch=[]
            if batch:flush(batch)
    if not count:raise ValueError('Empty corpus')
    es_request('POST',f'/{name}/_refresh')
    if collection.count()!=count or es_request('GET',f'/{name}/_count')['count']!=count:
        raise RetrievalUnavailable('Index counts differ; active pointer unchanged')
    config={'name':name,'count':count,'embedding_model':model,'fingerprint':fingerprint,'built_at':date.today().isoformat()}
    temp=pointer.with_suffix('.tmp')
    temp.write_text(json.dumps(config,indent=2))
    temp.replace(pointer)
    return config
