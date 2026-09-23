import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app import Document, Engine, create_app, redact

DOCS = json.loads((Path(__file__).parents[1]/'data/demo.json').read_text())

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(DOCS, tmp_path/'test.db', api_key='', embeddings=False, gpt=False))

def session(client):
    r = client.post('/api/sessions')
    assert r.status_code == 201
    return r.json()['session_id']

def ask(client, token, question='근로계약 임금'):
    return client.post(f'/api/sessions/{token}/messages', json={'question': question})

def test_health(client):
    assert client.get('/api/health').json() == {'status':'ok','documents':3,'demo':True}

def test_citations(client):
    r=ask(client, session(client))
    assert r.status_code==200
    answer=r.json()
    assert answer['sources'][0]['id']=='demo-work'
    assert answer['demo']
    for s in answer['sentences']:
        source=next(d for d in answer['sources'] if d['id']==s['source_id'])
        assert s['text'] in source['text']
    assert r.headers['cache-control']=='no-store'

def test_abstains(client):
    assert ask(client,session(client),'zzzzzzzzzz').json()['status']=='insufficient'

def test_multiturn_isolation_and_deletion(client):
    a,b=session(client),session(client)
    ask(client,a)
    assert ask(client,a,'그럼 관련 자료는?').json()['context_used']
    assert client.get('/api/sessions/'+b).json()['turns']==[]
    assert client.delete('/api/sessions/'+a).status_code==204
    assert ask(client,a).status_code==404
    assert ask(client,b).status_code==200

@pytest.mark.parametrize('value',['',' ','a','x'*1501])
def test_input_limits(client,value):
    assert ask(client,session(client),value).status_code==422

def test_redaction(client):
    token=session(client)
    ask(client,token,'근로계약 문의 test@example.com 010-1234-5678 900101-1234567')
    history=client.get('/api/sessions/'+token).text
    assert 'test@example.com' not in history and '010-1234-5678' not in history
    assert '900101-1234567' not in history

def test_expiry(client):
    token=session(client)
    with client.app.state.engine.db() as db:
        db.execute('UPDATE sessions SET expires=?',(time.time()-1,))
    assert ask(client,token).status_code==404

def test_invalid_urls():
    for url in ['javascript:alert(1)','https://law.go.kr.evil.test/','http://law.go.kr','https://user@law.go.kr']:
        with pytest.raises(ValidationError):Document.model_validate(dict(DOCS[0],url=url))

def test_duplicate_ids(tmp_path):
    with pytest.raises(ValueError): Engine([DOCS[0], DOCS[0]],tmp_path/'db')

def test_budget_limit(client):
    token=session(client)
    for _ in range(30): assert ask(client,token).status_code==200
    assert ask(client,token).status_code==429

def test_bad_gpt_citation_falls_back(client):
    engine=client.app.state.engine
    engine.gpt=True
    engine.openai=Mock(return_value={'choices':[{'message':{'content':json.dumps({'quotes':[{'source_id':'fabricated','quote':'invented law text'}]})}}]})
    answer=ask(client,session(client)).json()
    assert answer['warning'] and answer['generation']=='extractive'
    assert all('invented' not in s['text'] for s in answer['sentences'])

def test_valid_gpt_quote(client):
    engine=client.app.state.engine
    engine.gpt=True
    engine.openai=Mock(return_value={'choices':[{'message':{'content':json.dumps({'quotes':[{'source_id':'demo-work','quote':DOCS[0]['text']}]})}}]})
    assert ask(client,session(client)).json()['generation']=='gpt-verified-extract'

def test_gpt_no_evidence(client):
    engine=client.app.state.engine
    engine.gpt=True
    engine.openai=Mock(return_value={'choices':[{'message':{'content':'{"quotes":[]}'}}]})
    assert ask(client,session(client)).json()['status']=='insufficient'

def test_embedding_failure(client):
    engine=client.app.state.engine
    engine.embeddings=True
    engine.vector=Mock(side_effect=httpx.ConnectError('offline'))
    assert ask(client,session(client)).status_code==503

def test_semantic_vector_cache(tmp_path, monkeypatch):
    mock=Mock(return_value={'data':[{'embedding':[1.,0.,0.]}]})
    monkeypatch.setattr(Engine,'openai',mock)
    engine=Engine(DOCS,tmp_path/'db','test-key',True)
    assert mock.call_count==3
    Engine(DOCS,tmp_path/'db','test-key',True)
    assert mock.call_count==3
    assert engine.search('근로계약')

def test_sessions_persist(tmp_path):
    path=tmp_path/'db'
    first=Engine(DOCS,path)
    token=first.create_session()
    first.answer(token,'근로계약')
    assert len(Engine(DOCS,path).history(token))==1
