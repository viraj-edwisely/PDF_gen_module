"""Settings: providers, prices, limits and secrets. The only file to edit to change a model or a limit."""
import os

# One model per provider: Claude Sonnet is the reference, OpenAI and Gemini are mid-price models. price = (USD per 1M input tokens, USD per 1M output tokens).
PROVIDERS = {
    'Claude': {'model': 'claude-sonnet-5-5', 'key': 'ANTHROPIC_API_KEY', 'price': (2.0, 10.0), 'max_out': 64_000, 'concurrent': 6},
    'OpenAI': {'model': 'gpt-5.4-mini', 'key': 'OPENAI_API_KEY', 'price': (0.75, 4.50), 'max_out': 128_000, 'concurrent': 6},
    'Gemini': {'model': 'gemini-3-flash-preview', 'key': 'GOOGLE_SERVICE_ACCOUNT_JSON', 'price': (0.50, 3.0), 'max_out': 65_536, 'concurrent': 4},  # Vertex AI. Prices from trackers: confirm them and the model ID in your project
}
# max_out: the model's output limit (only the tokens actually written are paid for); concurrent: calls in flight at once
# per provider across all runs, so parallel topics do not trip its rate limit
RETRIES = 6               # retries of a rate-limited (429), overloaded or failed (5xx, timeout) call, with growing waits
EMBED_MODEL, EMBED_DIMS, EMBED_PRICE = 'text-embedding-3-small', 1536, 0.02  # price per 1M tokens

COST_CAP = 5.0            # USD per run; the run stops cleanly when reached
MAX_TOPICS = 20           # per run
TIMEZONE = 'Asia/Kolkata'  # times on the Usage page
MAX_URLS = 10            # PYQ source links or files per topic
MAX_BOOK_MB, MAX_PAGES = 100, 1500
WORKERS = 4               # PDFs (and book uploads) processed at the same time, across all runs
TOPIC_PARALLEL = 3        # PDFs of one GATE run processed at the same time
PARALLEL = 4              # model calls running at the same time inside one PDF
VERIFY_PROVIDER = 'Claude'    # the second model that re-checks GATE answer keys (falls back to the run's writer without its key)
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
