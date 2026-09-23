import pytest

@pytest.fixture(autouse=True)
def offline_test_mode(monkeypatch):
    # Unit tests must never invoke paid APIs or rely on external services.
    monkeypatch.setenv('RETRIEVAL_BACKEND','demo')
    monkeypatch.setenv('USE_GPT','0')
