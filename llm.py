"""One call for all providers: generate_json(provider, system, user) -> (object, usage, raw text).

Providers are asked for a single JSON object; we tidy and check it ourselves (content.py and the pipeline's repair loop),
because the providers' schema dialects do not fit our content JSON. Rate limits (429), overload and 5xx errors are
retried by the SDKs (RETRIES times, with growing waits that honour Retry-After), and at most `concurrent` calls per
provider are in flight at once. The system prompt is the same for every call of a run, so it is sent first and cached
where the provider supports it.
"""
import functools, importlib, json, re, threading
from config import PROVIDERS, RETRIES, cost, secret

SLOTS = {p: threading.BoundedSemaphore(c['concurrent']) for p, c in PROVIDERS.items()}
CUT_OFF = '{} reply was cut off at its length limit: write the same items more concisely (shorter explanations)'
GEMINI_LOCK = threading.Lock()      # functools.cache is not atomic: parallel first calls would each make a client


class LLMError(Exception):
    """usage: what the failed call cost, when tokens were spent (a (in, out, billed in) tuple inside the provider
    functions, a {'in', 'out', 'cost'} dict once it leaves generate_json)."""
    def __init__(self, message, raw='', usage=None):
        super().__init__(message); self.raw, self.usage = raw, usage


def _guess(system, user, text):
    """Rough usage (4 characters a token) of a reply given up on before the provider reported its usage."""
    n = len(system + user) // 4
    return n, len(text) // 4, n


def _claude(model, system, user, max_tokens):
    import anthropic
    with anthropic.Anthropic(api_key=secret('ANTHROPIC_API_KEY'), max_retries=RETRIES).messages.stream(
            model=model, max_tokens=max_tokens, system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
            messages=[{'role': 'user', 'content': user}], output_config={'effort': 'medium'}) as stream:
        sofar = ''
        for t in stream.text_stream:
            sofar += t
            if stuck(sofar): raise LLMError(STUCK.format('Claude'), sofar, _guess(system, user, sofar))
        msg = stream.get_final_message()
    text = ''.join(b.text for b in msg.content if b.type == 'text')
    u = msg.usage; read, write = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
    usage = (u.input_tokens + read + write, u.output_tokens, u.input_tokens + PROVIDERS['Claude']['cached'] * read + 1.25 * write)
    why = {'max_tokens': CUT_OFF.format('Claude'), 'refusal': 'Claude declined to answer',
           'model_context_window_exceeded': 'Claude reply was cut off: the request and reply filled its context window'}.get(msg.stop_reason)
    if why: raise LLMError(why, text, usage)
    return (text,) + usage


def _openai(model, system, user, max_tokens):
    from openai import OpenAI
    text, usage, finish = '', (0, 0, 0), None
    for ev in OpenAI(api_key=secret('OPENAI_API_KEY'), max_retries=RETRIES).chat.completions.create(
            model=model, max_completion_tokens=max_tokens, reasoning_effort='medium', stream=True, stream_options={'include_usage': True},     # reasoning tokens count towards the limit and the price
            response_format={'type': 'json_object'}, messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]):
        if ev.choices:
            text += ev.choices[0].delta.content or ''
            if stuck(text): raise LLMError(STUCK.format('OpenAI'), text, _guess(system, user, text))
            finish = ev.choices[0].finish_reason or finish
        if ev.usage:
            cached = getattr(ev.usage.prompt_tokens_details, 'cached_tokens', 0) or 0
            usage = (ev.usage.prompt_tokens, ev.usage.completion_tokens, ev.usage.prompt_tokens - (1 - PROVIDERS['OpenAI']['cached']) * cached)    # automatic prompt caching
    if finish == 'length': raise LLMError(CUT_OFF.format('OpenAI'), text, usage)      # checked after the loop: the usage comes last
    if finish == 'content_filter': raise LLMError('OpenAI withheld the reply (content filter)', text, usage)
    return (text,) + usage


@functools.cache
def _gemini_client():
    """Gemini through Vertex AI, signed in with the service-account JSON (no API key). Made once and kept:
    the library closes its connection when a client is garbage-collected, which breaks a stream still being read."""
    from google import genai
    from google.oauth2 import service_account
    info = secret('GOOGLE_SERVICE_ACCOUNT_JSON')
    # pasted as a JSON string or as a TOML table; strict=False because TOML """...""" turns the key's \n into real line breaks
    info = json.loads(info, strict=False) if isinstance(info, str) else dict(info)
    creds = service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/cloud-platform'])
    args = dict(project=info['project_id'], location=secret('GOOGLE_CLOUD_LOCATION') or 'global', credentials=creds,
                http_options=genai.types.HttpOptions(retry_options=genai.types.HttpRetryOptions(attempts=RETRIES + 1)))   # retries 408, 429, 5xx
    try: return genai.Client(enterprise=True, **args)      # google-genai 2.x
    except TypeError: return genai.Client(vertexai=True, **args)    # google-genai 1.x


def _gemini(model, system, user, max_tokens):
    from google import genai
    text, usage, finish, blocked = '', (0, 0, 0), '', ''
    cfg = genai.types.GenerateContentConfig(system_instruction=system, response_mime_type='application/json', max_output_tokens=max_tokens,
                                          thinking_config=genai.types.ThinkingConfig(thinking_level='medium'))     # Gemini 3: thinking counts towards the output limit and the price
    with GEMINI_LOCK: client = _gemini_client()      # a local reference keeps the client alive while its stream is read
    for ch in client.models.generate_content_stream(model=model, contents=user, config=cfg):
        text += ch.text or ''
        if stuck(text): raise LLMError(STUCK.format('Gemini'), text, _guess(system, user, text))
        if ch.candidates and ch.candidates[0].finish_reason: finish = str(ch.candidates[0].finish_reason).rsplit('.', 1)[-1]
        if ch.prompt_feedback and ch.prompt_feedback.block_reason: blocked = str(ch.prompt_feedback.block_reason).rsplit('.', 1)[-1]
        if ch.usage_metadata:
            m = ch.usage_metadata; cached = m.cached_content_token_count or 0
            usage = (m.prompt_token_count or 0, (m.candidates_token_count or 0) + (m.thoughts_token_count or 0), (m.prompt_token_count or 0) - (1 - PROVIDERS['Gemini']['cached']) * cached)
    if finish == 'MAX_TOKENS': raise LLMError(CUT_OFF.format('Gemini'), text, usage)
    if blocked or finish in ('SAFETY', 'RECITATION', 'PROHIBITED_CONTENT', 'BLOCKLIST', 'SPII'):
        raise LLMError(f'Gemini blocked the reply ({blocked or finish})', text, usage)
    return (text,) + usage


CALLS = {'Claude': _claude, 'OpenAI': _openai, 'Gemini': _gemini}


# LaTeX commands that start with a letter JSON reads as an escape: "\frac" written with one backslash would silently
# become a form feed + "rac". \b \f \r \t followed by a letter are always LaTeX; \n followed by letters is a line break
# unless it spells one of these commands
TEX_WORDS = set('nu nabla ne neq neg not notin nmid ni nolimits nleq ngeq nless ngtr nexists newline nsubseteq nsupseteq ncong nsim '
                'nparallel nearrow nwarrow natural noindent nonumber notag nleftarrow nrightarrow nLeftarrow nRightarrow'.split())


def fix_escapes(text):
    """Double the single backslash of LaTeX commands (\\frac) and symbols (\\{ \\, \\% \\_) inside JSON text, so they survive json.loads."""
    def one(m):
        lead, word, after = m.group(1), m.group(2), m.string[m.end():m.end() + 1]
        tex = (word[0] not in 'nrtu' or (word[0] in 'rt' and len(word) > 1) or (word[0] == 'u' and not re.fullmatch(r'u[0-9a-fA-F]{4}', word))
               or (word in TEX_WORDS and not (len(word) == 2 and after in ('.', ')'))))    # "\ni.e." or "\ne)" is a line break
        return lead + ('\\\\' if tex else '\\') + word
    text = re.sub(r'(?<!\\)((?:\\\\)*)\\(u[0-9a-fA-F]{4}|[A-Za-z]+)', one, text)       # ° is one escape, \underline a command
    return re.sub(r'(?<!\\)((?:\\\\)*)\\([^"\\/A-Za-z])', lambda m: m.group(1) + '\\\\' + m.group(2), text)   # not a JSON escape


def loads(text):
    return json.loads(fix_escapes(text), strict=False)      # strict=False: a raw line break inside a string is kept


def parse_json(text):
    """Pull the JSON object out of a reply, tolerating code fences, a sentence (even with braces) before or after it,
    a single object wrapped in a list, and LaTeX with single backslashes."""
    text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    text = re.sub(r'(?<!\\)((?:\\\\)*)\\u0000', r'\1', text).replace('\x00', '')     # a NUL character cannot be stored in the database
    fixed = fix_escapes(text)
    m = re.search(r'\{\s*["}]', fixed)          # where an object starts; "{x}" in a sentence does not
    if not fixed.startswith('[') and not m: raise LLMError('the model did not return a JSON object', text)
    try: out = json.JSONDecoder(strict=False).raw_decode(fixed, 0 if fixed.startswith('[') else m.start())[0]    # text after the JSON is ignored
    except json.JSONDecodeError as e: raise LLMError(f'the model returned invalid JSON: {e}', text)
    if isinstance(out, list) and len(out) == 1: out = out[0]
    if not isinstance(out, dict): raise LLMError('the model did not return a JSON object', text)
    return out


def stuck(text):
    """True when the reply has started repeating a few characters over and over (e.g. "}]}]}]..."): it would run to the length limit.
    The window is long, so a legitimately repetitive list ("0, 0, 0, ...") is not mistaken for it."""
    tail = text[-3000:]
    return len(tail) == 3000 and any(tail[n:] == tail[:-n] for n in range(1, 9))


STUCK = '{} reply got stuck repeating the same characters; write each item once, as compact JSON'


@functools.cache
def _transient():
    """Errors worth another try: a dropped connection, or an API error of whichever provider SDKs are installed (also one sent mid-stream)."""
    kinds = []
    for mod, name in (('anthropic', 'APIError'), ('openai', 'APIError'), ('google.genai.errors', 'APIError'), ('httpx', 'TransportError')):
        try: kinds.append(getattr(importlib.import_module(mod), name))
        except ImportError: pass
    return tuple(kinds)


def generate_json(provider, system, user, max_tokens=None):
    """Returns (parsed object, {'in': tokens, 'out': tokens, 'cost': USD}, raw text). Waits for a free slot of the provider.
    A call that fails on a transient error is made up to twice more; every failure is raised as an LLMError with its usage."""
    bill = lambda t_in, t_out, billed_in: {'in': t_in, 'out': t_out, 'cost': cost(provider, billed_in, t_out)}
    for attempt in range(3):
        try:
            with SLOTS[provider]:
                text, *u = CALLS[provider](PROVIDERS[provider]['model'], system, user, max_tokens or PROVIDERS[provider]['max_out'])
            break
        except LLMError as e:
            if e.usage: e.usage = bill(*e.usage)
            raise
        except _transient() as e:
            if attempt == 2: raise LLMError(f'{provider} call failed: {type(e).__name__}: {e}') from e
    usage = bill(*u)
    try: return parse_json(text), usage, text
    except LLMError as e: e.usage = usage; raise


def ping(provider):
    """A tiny call that proves the key and the model ID work. Returns None or the error text."""
    try:
        out, _, _ = generate_json(provider, 'Reply with JSON only.', 'Return {"ok": true}', max_tokens=2000)
        return None if out.get('ok') else f'unexpected reply: {out}'
    except Exception as e:
        return f'{type(e).__name__}: {e}'[:400]


def embed(texts):
    """OpenAI embeddings for a list of texts (the library uses one fixed model). Returns a list of vectors."""
    from openai import OpenAI
    from config import EMBED_MODEL
    client, out = OpenAI(api_key=secret('OPENAI_API_KEY'), max_retries=RETRIES), []
    for i in range(0, len(texts), 100):
        out += [d.embedding for d in client.embeddings.create(model=EMBED_MODEL, input=[t[:8000] for t in texts[i:i + 100]]).data]
    return out
