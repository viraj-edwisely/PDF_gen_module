"""Settings: providers, prices, limits and secrets. The only file to edit to change a model or a limit."""
import os

# One model per provider (OpenAI and Gemini are on the cheaper tier while we compare quality). price = (USD per 1M input tokens, USD per 1M output tokens).
PROVIDERS = {
    'Claude': {'model': 'claude-sonnet-5-5', 'key': 'ANTHROPIC_API_KEY', 'price': (2.0, 10.0)},
    'OpenAI': {'model': 'gpt-4.1-mini', 'key': 'OPENAI_API_KEY', 'price': (0.40, 1.60)},
    'Gemini': {'model': 'gemini-2.5-flash', 'key': 'GOOGLE_SERVICE_ACCOUNT_JSON', 'price': (0.30, 2.50)},  # Vertex AI (confirm the price and that 2.5 is not retired on Vertex)
}
EMBED_MODEL, EMBED_DIMS, EMBED_PRICE = 'text-embedding-3-small', 1536, 0.02  # price per 1M tokens

COST_CAP = 5.0            # USD per run; the run stops cleanly when reached
MAX_TOPICS = 20           # per run
MAX_URLS = 10             # PYQ source URLs per run
MAX_BOOK_MB, MAX_PAGES = 100, 1500
WORKERS = 2               # runs processed at the same time
PARALLEL = 4              # model calls running at the same time inside one PDF
SCOPE_TOKEN_BUDGET = 40_000   # scope text up to this size is sent whole, in page order
TOPIC_TOKEN_BUDGET = 8_000    # per-topic retrieval budget for larger scopes
STALE_SECONDS = 60        # a running run with an older heartbeat shows as interrupted


def secret(name):
    """Environment variable first (tests, local runs), then Streamlit secrets."""
    if os.environ.get(name): return os.environ[name]
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def cost(provider, tokens_in, tokens_out):
    p_in, p_out = PROVIDERS[provider]['price']
    return (tokens_in * p_in + tokens_out * p_out) / 1e6
