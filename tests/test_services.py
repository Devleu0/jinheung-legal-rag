"""Opt-in REAL Elasticsearch/Chroma test, deterministic test vectors only.
Run after docker compose up, with requirements-rag installed. No OpenAI calls.
"""
import json
import os
from pathlib import Path
import pytest
from backend import hybrid

@pytest.mark.skipif(os.getenv('RUN_SERVICE_TESTS')!='1',reason='Requires real ES/Nori and Chroma services')
def test_real_dual_index_roundtrip(tmp_path,monkeypatch):
    class TestVectors:
        def embed_documents(self,texts):
            return [[1.,0.,0.] if '임금' in text else [0.,1.,0.] for text in texts]
        def embed_query(self,text):
            return self.embed_documents([text])[0]
    vector=TestVectors()
    monkeypatch.setattr(hybrid,'embeddings',lambda:vector)
    docs=[]
    for i,text in enumerate(['합성 테스트 임금 조항입니다.','합성 테스트 소음 조항입니다.']):
        docs.append({'id':f'integration-only-{i}','parent_id':f'parent-{i}','title':'합성 테스트 자료',
                     'kind':'law','locator':f'테스트 {i}','text':text,'url':'https://www.law.go.kr/',
                     'effective_date':'2026-09-23','retrieved_at':'2026-09-23'})
    corpus=tmp_path/'test.jsonl'
    corpus.write_text('\n'.join(json.dumps(d,ensure_ascii=False) for d in docs))
    pointer=tmp_path/'pointer.json'
    config=hybrid.build_index([corpus],pointer)
    assert config['count']==2
    retriever=hybrid.HybridRetriever(pointer,embedder=vector)
    result=retriever.search('임금','rrf')
    assert result[0]['id']=='integration-only-0'
    assert set(result[0]['retrieval_trace']['channels'])=={'bm25','dense'}
    # Test indexes are retained for inspection; never delete an unknown collection/index.
