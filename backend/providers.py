"""Server-owned chat provider settings; embedding configuration is independent."""
import os

GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/'
PROVIDERS = ('openai', 'gemini')


def default_provider():
    provider = os.getenv('CHAT_PROVIDER', 'openai')
    if provider not in PROVIDERS:
        raise ValueError('CHAT_PROVIDER must be openai or gemini')
    return provider


def chat_model(provider):
    if provider == 'gemini':
        return os.getenv('GEMINI_CHAT_MODEL', 'gemini-2.5-flash')
    if provider == 'openai':
        return os.getenv('CHAT_MODEL', 'gpt-4o-mini')
    raise ValueError('Unknown chat provider')


def api_key(provider, openai_key=None):
    if provider == 'gemini':
        return os.getenv('GEMINI_API_KEY', '')
    if provider == 'openai':
        return os.getenv('OPENAI_API_KEY', '') if openai_key is None else openai_key
    raise ValueError('Unknown chat provider')
