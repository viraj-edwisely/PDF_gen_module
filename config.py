"""Settings: model, prices, limits and secrets. The only file to edit to change a model or a limit."""
import os

# The one writer model. price = (USD per 1M input tokens, USD per 1M output tokens; reasoning tokens are billed as output);
# cached: price of a cache read as a share of the input price; max_out: the model's output limit (only the tokens written are paid for);
# concurrent: calls in flight at once across all runs, so parallel topics do not trip the rate limit.
# Thinking level: the user picks one per run; higher levels reason longer (better, slower, dearer).
MODEL = {'name': 'gpt-6-luna', 'price': (0.10, 0.50), 'cached': 0.1, 'max_out': 128_000, 'concurrent': 6}
EFFORTS, DEFAULT_EFFORT = ('low', 'medium', 'high'), 'medium'
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
SCOPE_TOKEN_BUDGET = 16_000   # scope text up to this size is sent whole, in page order (it goes into 4 calls, so larger scopes are searched)
TOPIC_TOKEN_BUDGET = 8_000    # retrieval budget per call for larger scopes (GATE notes and questions search their own sections)
STALE_SECONDS = 60        # a running run with an older heartbeat shows as interrupted


def secret(name):
    """Environment variable first (tests, local runs), then Streamlit secrets."""
    if os.environ.get(name): return os.environ[name]
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def cost(tokens_in, tokens_out):
    p_in, p_out = MODEL['price']
    return (tokens_in * p_in + tokens_out * p_out) / 1e6
