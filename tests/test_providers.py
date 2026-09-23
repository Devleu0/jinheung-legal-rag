"""Offline provider contracts: no paid API requests."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import Engine, create_app
from backend.generation import model
from backend.providers import GEMINI_BASE_URL

DOCS = json.loads((Path(__file__).parents[1] / 'data/demo.json').read_text())

@pytest.fixture
def gemini(tmp_path, monkeypatch):
    monkeypatch.setenv('CHAT_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'secret-gemini')
    return TestClient(create_app(DOCS, tmp_path/'db', api_key='', embeddings=False,
                                 gpt=True, retrieval_backend='demo'))


def ask(client, provider=None):
    token = client.post('/api/sessions').json()['session_id']
    body = {'question': '근로계약 임금'}
    if provider is not None:
        body['provider'] = provider
    return client.post(f'/api/sessions/{token}/messages', json=body)


def test_models_do_not_expose_keys(gemini):
    response = gemini.get('/api/models')
    assert 'secret-gemini' not in response.text
    assert response.json()['default_provider'] == 'gemini'
    assert [p['available'] for p in response.json()['providers']] == [False, True]


def test_gemini_transport_and_verified_quote(gemini, monkeypatch):
    def handler(request):
        assert str(request.url) == GEMINI_BASE_URL + 'chat/completions'
        assert request.headers['authorization'] == 'Bearer secret-gemini'
        assert json.loads(request.content)['model'] == 'gemini-2.5-flash'
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(
            {'quotes': [{'source_id': DOCS[0]['id'], 'quote': DOCS[0]['text']}]})}}]})
    real_client = httpx.Client
    monkeypatch.setattr('backend.app.httpx.Client', lambda **kwargs: real_client(
        transport=httpx.MockTransport(handler), **kwargs))
    result = ask(gemini, 'gemini').json()
    assert result['generation'] == 'gemini-verified-extract'
    assert result['provider'] == 'gemini'
    assert result['sentences'][0]['text'] == DOCS[0]['text']


def test_invalid_and_unavailable_provider(gemini):
    assert ask(gemini, 'unknown').status_code == 422
    assert ask(gemini, 'openai').status_code == 400


@pytest.mark.parametrize('payload', [
    {'choices': [{'message': {'content': '{invalid'}}]},
    {'choices': [{'message': {'content': '{"quotes":[{"source_id":"fake","quote":"fabricated evidence"}]}'}}]},
    {'choices': []},
])
def test_gemini_bad_output_falls_back(gemini, payload):
    gemini.app.state.engine.chat = Mock(return_value=payload)
    result = ask(gemini).json()
    assert result['generation'] == 'extractive'
    assert result['warning']
    assert result['sentences']


def test_gemini_failure_does_not_call_openai(gemini):
    engine = gemini.app.state.engine
    engine.chat = Mock(side_effect=httpx.ConnectError('offline'))
    engine.openai = Mock()
    assert ask(gemini).json()['generation'] == 'extractive'
    engine.openai.assert_not_called()


def test_embedding_key_still_required(tmp_path, monkeypatch):
    monkeypatch.setenv('CHAT_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    with pytest.raises(ValueError, match='임베딩'):
        Engine(DOCS, tmp_path/'db', embeddings=True, gpt=True)


def test_generation_factory_uses_gemini_endpoint(monkeypatch):
    constructor = Mock()
    monkeypatch.setitem(sys.modules, 'langchain_openai', SimpleNamespace(ChatOpenAI=constructor))
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    model('gemini')
    assert constructor.call_args.kwargs['base_url'] == GEMINI_BASE_URL
    assert constructor.call_args.kwargs['api_key'] == 'test-key'
    model('openai', 'openai-key')
    assert 'base_url' not in constructor.call_args.kwargs
    assert constructor.call_args.kwargs['api_key'] == 'openai-key'


def test_production_routes_rewrite_and_generation(gemini, monkeypatch):
    engine = gemini.app.state.engine
    engine.retriever = Mock(config={'count': 3})
    engine.retriever.search.return_value = DOCS
    generate = Mock(return_value=[{'text': DOCS[0]['text'], 'source_id': DOCS[0]['id']}])
    rewrite = Mock(return_value='근로계약 임금')
    monkeypatch.setattr('backend.generation.generate', generate)
    monkeypatch.setattr('backend.generation.rewrite', rewrite)
    token = engine.create_session()
    engine.answer(token, '근로계약 임금', 'gemini')
    result = engine.answer(token, '그럼 임금은?', 'gemini')
    assert result['generation'] == 'langchain-gemini-reviewed'
    assert generate.call_args.kwargs['provider'] == 'gemini'
    assert rewrite.call_args.kwargs['provider'] == 'gemini'
    # Selection is per request, not mutable global engine state.
    engine.key = 'openai-key'
    engine.answer(token, '근로계약 임금', 'openai')
    assert generate.call_args.kwargs['provider'] == 'openai'
    assert engine.provider == 'gemini'


def test_disabled_generation(tmp_path, monkeypatch):
    monkeypatch.setenv('CHAT_PROVIDER', 'gemini')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    client = TestClient(create_app(DOCS, tmp_path/'db', api_key='', gpt=False,
                                  embeddings=False, retrieval_backend='demo'))
    assert not client.get('/api/models').json()['enabled']
    assert ask(client, 'gemini').status_code == 400
    assert ask(client).json()['provider'] is None
