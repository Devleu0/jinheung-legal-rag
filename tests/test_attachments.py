import json
import httpx
import pytest
from tools.download_attachments import download


def test_attachment_resume_advances_past_completed_files(tmp_path,monkeypatch):
    manifest=tmp_path/'links.jsonl'
    manifest.write_text('\n'.join(json.dumps({'url':f'https://www.law.go.kr/LSW/flDownload.do?flSeq={i}'}) for i in [1,2]))
    original=httpx.Client
    monkeypatch.setattr('tools.download_attachments.time.sleep',lambda _:None)
    monkeypatch.setattr('tools.download_attachments.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(lambda _:httpx.Response(200,content=b'fixture-binary',headers={'content-type':'application/octet-stream'})),**kw))
    out=tmp_path/'assets'
    download(manifest,out,limit=1)
    assert len(list(out.glob('*.json')))==1
    download(manifest,out,limit=1)
    assert len(list(out.glob('*.json')))==2


def test_attachment_rejects_external_host(tmp_path):
    manifest=tmp_path/'links.jsonl'
    manifest.write_text(json.dumps({'url':'https://evil.invalid/LSW/flDownload.do?flSeq=1'}))
    with pytest.raises(ValueError):download(manifest,tmp_path/'assets')
