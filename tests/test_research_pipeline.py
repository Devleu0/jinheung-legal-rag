"""Synthetic contract fixtures derived from official field definitions, NOT live law data."""
import argparse
import json
from unittest.mock import Mock

import httpx
import pytest
from backend.hybrid import HybridRetriever, RetrievalUnavailable, bm25_query, fuse
from backend.generation import Answer, Sentence, validate
from tools.law_sync import Api, chunks, detail_params, parse_list, sync, export

LAW = '<법령><기본정보><법령명_한글>테스트법</법령명_한글><법령ID>123</법령ID></기본정보><조문><조문단위><조문번호>2</조문번호><조문여부>조문</조문여부><조문제목>조건</조문제목><조문내용>테스트용 본문입니다.</조문내용><항><항내용>다만 예외 조건을 함께 확인한다.</항내용></항></조문단위></조문></법령>'.encode()
ITEM = {'법령일련번호':'123','시행일자':'20260923','현행연혁코드':'현행'}
LIST = '<LawSearch><totalCnt>1</totalCnt><page>1</page><law><법령일련번호>123</법령일련번호><시행일자>20260923</시행일자><현행연혁코드>현행</현행연혁코드></law></LawSearch>'.encode()


def test_mst_and_effective_date_not_law_id():
    assert detail_params(ITEM,'eflaw')=={'MST':'123','efYd':'20260923'}
    assert detail_params({'판례일련번호':'99'},'prec')=={'ID':'99'}


def test_list_and_error_detection():
    assert parse_list(LIST,'eflaw')[0]==1
    with pytest.raises(ValueError):parse_list(b'<error>not approved</error>','eflaw')
    with pytest.raises(ValueError):parse_list(b'<LawSearch><totalCnt>1</totalCnt></LawSearch>','eflaw')


def test_chunk_preserves_proviso_offsets():
    docs=list(chunks(LAW,ITEM,'eflaw','2026-09-23',size=20,overlap=5))
    assert len(docs)>1
    assert all(d['end_char']-d['start_char']==len(d['text']) for d in docs)
    assert any('예외' in d['text'] for d in docs)
    assert len({d['parent_id'] for d in docs})==1


def test_case_metadata_and_html_breaks():
    raw='<PrecService><사건명>시연 사건</사건명><사건번호>2026다1</사건번호><선고일자>2026.09.01</선고일자><법원명>테스트법원</법원명><판례내용>문단1&lt;br/&gt;문단2 테스트 본문</판례내용><참조조문>테스트법 제2조</참조조문></PrecService>'.encode()
    docs=list(chunks(raw,{'판례일련번호':'99'},'prec','2026-09-23'))
    assert docs[0]['decision_date']=='2026-09-01'
    assert '\n' in docs[0]['text']
    assert docs[0]['reference_text']=='테스트법 제2조'


def args(tmp_path):
    return argparse.Namespace(target='eflaw',query='',nw='3',date_range='',out=tmp_path,refresh=False,max_pages=1,max_details=10)


def test_resume_export_checksum(tmp_path):
    api=Mock(used=2);api.get.side_effect=[LIST,LAW]
    assert sync(args(tmp_path),api)==0
    second=Mock(used=0)
    assert sync(args(tmp_path),second)==0
    second.get.assert_not_called()
    output=tmp_path/'corpus.jsonl'
    export(tmp_path,output)
    assert json.loads(output.read_text().splitlines()[0])['kind']=='law'
    next((tmp_path/'raw').glob('*.xml')).write_bytes(b'corrupted')
    with pytest.raises(ValueError):export(tmp_path,output)


def test_failed_detail_not_marked_complete(tmp_path):
    api=Mock(used=2);api.get.side_effect=[LIST,b'<error/>']
    assert sync(args(tmp_path),api)==2
    with pytest.raises(ValueError):export(tmp_path,tmp_path/'corpus.jsonl')
    retry=Mock(used=1);retry.get.return_value=LAW
    assert sync(args(tmp_path),retry)==0
    assert retry.get.call_count==1


def test_scope_change_rejected(tmp_path):
    api=Mock(used=2);api.get.side_effect=[LIST,LAW]
    sync(args(tmp_path),api)
    changed=args(tmp_path);changed.query='other'
    with pytest.raises(ValueError):sync(changed,api)


def test_rate_retry_and_credentials_not_in_error(monkeypatch):
    monkeypatch.setattr('tools.law_sync.time.sleep',lambda _:None)
    calls=[]
    def handler(req):
        calls.append(req)
        if len(calls)==1:return httpx.Response(429,headers={'Retry-After':'0'})
        return httpx.Response(200,content=LIST)
    api=Api('private-test-auth',transport=httpx.MockTransport(handler))
    assert api.get('lawSearch.do',{'target':'eflaw'})==LIST
    assert len(calls)==2 and calls[-1].url.params['OC']=='private-test-auth'
    with pytest.raises(ValueError):Api('')


def test_adaptive_fusion_is_measurably_distinct():
    baseline=fuse(['a','b'],['c','b'],'제2조','rrf')
    exact=fuse(['a','b'],['c','b'],'제2조','adaptive')
    natural=fuse(['a','b'],['c','b'],'보증금 안 줘요','adaptive')
    assert exact[0][1]['weights']=={'bm25':2.,'dense':1.}
    assert natural[0][1]['weights']=={'bm25':1.,'dense':2.}
    assert baseline!=exact
    assert [i for i,_ in fuse(['a'],['b'],'q','bm25')]==['a']


def test_real_adapters_query_contract(tmp_path):
    config={'name':'legal-test','count':2,'embedding_model':'text-embedding-3-small'}
    pointer=tmp_path/'active.json';pointer.write_text(json.dumps(config))
    doc={'id':'a','parent_id':'p','text':'테스트 문서','kind':'law'}
    request=Mock(side_effect=[{'count':2},{'hits':{'hits':[{'_id':'a','_score':2}]}},{'docs':[{'_id':'a','found':True,'_source':{'payload':doc}}]}])
    collection=Mock();collection.count.return_value=2
    collection.query.return_value={'ids':[['a','b']],'distances':[[0.1,0.9]]}
    embedder=Mock();embedder.embed_query.return_value=[0.1,0.2]
    retriever=HybridRetriever(pointer,embedder,collection,request)
    output=retriever.search('임금','adaptive-diverse')
    assert output[0]['retrieval_trace']['channels']==['bm25','dense']
    assert collection.query.call_args.kwargs['query_embeddings']==[[0.1,0.2]]
    assert 'multi_match' in request.call_args_list[1].kwargs['json']['query']


def test_missing_index_fails_closed(tmp_path):
    pointer=tmp_path/'active.json'
    pointer.write_text(json.dumps({'name':'x','count':3,'embedding_model':'text-embedding-3-small'}))
    collection=Mock();collection.count.return_value=2
    with pytest.raises(RetrievalUnavailable):HybridRetriever(pointer,Mock(),collection,Mock())


def test_sentence_citation_validation():
    doc={'id':'law:1','text':'조건과 예외를 함께 확인해야 합니다.'}
    answer=Answer(sentences=[Sentence(text='조건과 예외를 확인합니다.',source_id='law:1',evidence_quote=doc['text'])])
    assert validate(answer,[doc])[0]['source_id']=='law:1'
    answer.sentences[0].evidence_quote='실제로는 존재하지 않는 인용문'
    with pytest.raises(ValueError):validate(answer,[doc])
