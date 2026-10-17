"""One call for all providers: generate_json(provider, system, user) -> (object, usage, raw text).

Providers are asked for a single JSON object; we tidy and check it ourselves (content.py and the pipeline's repair loop),
because the providers' schema dialects do not fit our content JSON. Rate limits (429), overload and 5xx errors are
retried by the SDKs (RETRIES times, with growing waits that honour Retry-After), and at most `concurrent` calls per
provider are in flight at once. The system prompt is the same for every call of a run, so it is sent first and cached
where the provider supports it.
"""
import functools, json, re, threading
from config import PROVIDERS, RETRIES, cost, secret

SLOTS = {p: threading.BoundedSemaphore(c['concurrent']) for p, c in PROVIDERS.items()}
CUT_OFF = '{} reply was cut off at its length limit: write the same items more concisely (shorter explanations)'


class LLMError(Exception):
    def __init__(self, message, raw=''):
        super().__init__(message); self.raw = raw


def _claude(model, system, user, max_tokens):
    import anthropic
    with anthropic.Anthropic(api_key=secret('ANTHROPIC_API_KEY'), max_retries=RETRIES).messages.stream(
            model=model, max_tokens=max_tokens, system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
            messages=[{'role': 'user', 'content': user}], output_config={'effort': 'medium'}) as stream:
        sofar = ''
        for t in stream.text_stream:
            sofar += t
            if stuck(sofar): raise LLMError(STUCK.format('Claude'), sofar)
        msg = stream.get_final_message()
    text = ''.join(b.text for b in msg.content if b.type == 'text')
    if msg.stop_reason == 'max_tokens': raise LLMError(CUT_OFF.format('Claude'), text)
    if msg.stop_reason == 'refusal': raise LLMError('Claude declined to answer', text)
    u = msg.usage; read, write = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
    return text, u.input_tokens + read + write, u.output_tokens, u.input_tokens + PROVIDERS['Claude']['cached'] * read + 1.25 * write


def _openai(model, system, user, max_tokens):
    from openai import OpenAI
    text, usage = '', (0, 0, 0)
    for ev in OpenAI(api_key=secret('OPENAI_API_KEY'), max_retries=RETRIES).chat.completions.create(
            model=model, max_completion_tokens=max_tokens, reasoning_effort='medium', stream=True, stream_options={'include_usage': True},     # reasoning tokens count towards the limit and the price
            response_format={'type': 'json_object'}, messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]):
        if ev.choices:
            text += ev.choices[0].delta.content or ''
            if stuck(text): raise LLMError(STUCK.format('OpenAI'), text)
            if ev.choices[0].finish_reason == 'length': raise LLMError(CUT_OFF.format('OpenAI'), text)
        if ev.usage:
            cached = getattr(ev.usage.prompt_tokens_details, 'cached_tokens', 0) or 0
            usage = (ev.usage.prompt_tokens, ev.usage.completion_tokens, ev.usage.prompt_tokens - (1 - PROVIDERS['OpenAI']['cached']) * cached)    # automatic prompt caching
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
    text, usage = '', (0, 0, 0)
    cfg = genai.types.GenerateContentConfig(system_instruction=system, response_mime_type='application/json', max_output_tokens=max_tokens,
                                          thinking_config=genai.types.ThinkingConfig(thinking_level='medium'))     # Gemini 3: thinking counts towards the output limit and the price
    for ch in _gemini_client().models.generate_content_stream(model=model, contents=user, config=cfg):
        text += ch.text or ''
        if stuck(text): raise LLMError(STUCK.format('Gemini'), text)
        if ch.candidates and str(ch.candidates[0].finish_reason).endswith('MAX_TOKENS'): raise LLMError(CUT_OFF.format('Gemini'), text)
        if ch.usage_metadata:
            m = ch.usage_metadata; cached = m.cached_content_token_count or 0
            usage = (m.prompt_token_count or 0, (m.candidates_token_count or 0) + (m.thoughts_token_count or 0), (m.prompt_token_count or 0) - (1 - PROVIDERS['Gemini']['cached']) * cached)
    return (text,) + usage


CALLS = {'Claude': _claude, 'OpenAI': _openai, 'Gemini': _gemini}


# LaTeX commands that start with a letter JSON reads as an escape (\f, \t, \r, \b, \n): "\frac" written with one
# backslash would silently become a form feed + "rac", "\right" a carriage return + "ight"
TEX_WORDS = set('frac tfrac theta tau tan tanh times text textbf textrm to top tilde triangle right rightarrow rho rangle rceil rfloor '
                'beta bar begin binom big bigl bigr bf bullet boldsymbol nu nabla ne neq neg not notin nmid ni nolimits forall flat frown'.split())


def fix_escapes(text):
    """Double the single backslash of LaTeX commands (\\frac) and symbols (\\{ \\, \\% \\_) inside JSON text, so they survive json.loads."""
    def one(m):
        lead, word = m.group(1), m.group(2)
        bad = word[0] not in 'bfnrtu' or word in TEX_WORDS or (word[0] == 'u' and not re.match(r'u[0-9a-fA-F]{4}', word))
        return lead + ('\\\\' if bad else '\\') + word
    text = re.sub(r'(?<!\\)((?:\\\\)*)\\([A-Za-z]+)', one, text)
    return re.sub(r'(?<!\\)((?:\\\\)*)\\([^"\\/A-Za-z])', lambda m: m.group(1) + '\\\\' + m.group(2), text)   # not a JSON escape


def loads(text):
    return json.loads(fix_escapes(text), strict=False)      # strict=False: a raw line break inside a string is kept


def parse_json(text):
    """Pull the JSON object out of a reply, tolerating code fences, a sentence before or after it, and LaTeX with single backslashes."""
    text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip().replace('\\u0000', '')    # a NUL character cannot be stored in the database
    a, b = text.find('{'), text.rfind('}')
    if a < 0 or b < a: raise LLMError('the model did not return a JSON object', text)
    try: return loads(text[a:b + 1])
    except json.JSONDecodeError as e: raise LLMError(f'the model returned invalid JSON: {e}', text)


def stuck(text):
    """True when the reply has started repeating a few characters over and over (e.g. "}]}]}]..."): it would run to the length limit."""
    tail = text[-400:]
    return len(tail) == 400 and any(tail[n:] == tail[:-n] for n in range(1, 9))


STUCK = '{} reply got stuck repeating the same characters; write each item once, as compact JSON'


def generate_json(provider, system, user, max_tokens=None):
    """Returns (parsed object, {'in': tokens, 'out': tokens, 'cost': USD}, raw text). Waits for a free slot of the provider."""
    with SLOTS[provider]:
        text, t_in, t_out, billed_in = CALLS[provider](PROVIDERS[provider]['model'], system, user, max_tokens or PROVIDERS[provider]['max_out'])
    return parse_json(text), {'in': t_in, 'out': t_out, 'cost': cost(provider, billed_in, t_out)}, text


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
    client, out = OpenAI(api_key=secret('OPENAI_API_KEY')), []
    for i in range(0, len(texts), 100):
        out += [d.embedding for d in client.embeddings.create(model=EMBED_MODEL, input=[t[:8000] for t in texts[i:i + 100]]).data]
    return out
