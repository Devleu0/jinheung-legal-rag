"""Integration checks after frontend build and corpus validation CLI."""
import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_validated_import(tmp_path):
    docs = json.loads((ROOT/'data/demo.json').read_text())
    # Synthetic test input only; this is not a verified law.
    docs[0]['kind'] = 'law'
    source, output = tmp_path/'input.json', tmp_path/'legal.json'
    source.write_text(json.dumps([docs[0]]))
    result = subprocess.run([sys.executable, 'scripts/import_data.py', str(source), '--output', str(output)], cwd=ROOT, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())[0]['id'] == 'demo-work'


def test_reject_demo_import(tmp_path):
    output = tmp_path/'legal.json'
    result = subprocess.run([sys.executable, 'scripts/import_data.py', 'data/demo.json', '--output', str(output)], cwd=ROOT, capture_output=True)
    assert result.returncode != 0
    assert not output.exists()


def test_frontend_delivery(tmp_path):
    # CI must build the frontend before running this test.
    client = TestClient(create_app(db_path=tmp_path/'chat.db', api_key='', embeddings=False, gpt=False))
    home = client.get('/')
    assert home.status_code == 200
    assert 'id="root"' in home.text
    assert client.get('/manifest.webmanifest').json()['display'] == 'standalone'
    assert client.get('/sw.js').status_code == 200
    assert client.get('/api/health').status_code == 200
