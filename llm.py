"""One call to the writer model: generate_json(system, user) -> (object, usage, raw text).

The model is asked for a single JSON object; we tidy and check it ourselves (content.py and the pipeline's repair loop),
because the API's schema dialect does not fit our content JSON. Rate limits (429), overload and 5xx errors are
retried by the SDK (RETRIES times, with growing waits that honour Retry-After), and at most `concurrent` calls are in
flight at once. The system prompt is the same for every call of a run, so it is sent first and cached automatically.
"""
import base64, functools, importlib, json, re, threading
from config import DEFAULT_EFFORT, IMAGE_MODEL, MODEL, RETRIES, cost, secret

SLOT = threading.BoundedSemaphore(MODEL['concurrent'])
CUT_OFF = '{} reply was cut off at its length limit: write the same items more concisely (shorter explanations)'


class LLMError(Exception):
    """usage: what the failed call cost, when tokens were spent (a (in, out, billed in) tuple inside the provider
    functions, a {'in', 'out', 'cost'} dict once it leaves generate_json)."""
    def __init__(self, message, raw='', usage=None):
        super().__init__(message); self.raw, self.usage = raw, usage


def _guess(system, user, text):
    """Rough usage (4 characters a token) of a reply given up on before the provider reported its usage."""
    n = len(system + user) // 4
    return n, len(text) // 4, n


def _openai(system, user, max_tokens, effort, images=()):
    from openai import OpenAI
    text, usage, finish = '', (0, 0, 0), None
    content = user if not images else [{'type': 'text', 'text': user}] + [            # PNGs shown to the model after the text, in order
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(png).decode(), 'detail': 'high'}} for png in images]
    for ev in OpenAI(api_key=secret('OPENAI_API_KEY'), max_retries=RETRIES).chat.completions.create(
            model=MODEL['name'], max_completion_tokens=max_tokens, reasoning_effort=effort, stream=True, stream_options={'include_usage': True},     # reasoning tokens count towards the limit and the price
            response_format={'type': 'json_object'}, messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': content}]):
        if ev.choices:
            text += ev.choices[0].delta.content or ''
            if stuck(text): raise LLMError(STUCK.format('OpenAI'), text, _guess(system, user, text))
            finish = ev.choices[0].finish_reason or finish
        if ev.usage:
            cached = getattr(ev.usage.prompt_tokens_details, 'cached_tokens', 0) or 0
            usage = (ev.usage.prompt_tokens, ev.usage.completion_tokens, ev.usage.prompt_tokens - (1 - MODEL['cached']) * cached)    # automatic prompt caching
    if finish == 'length': raise LLMError(CUT_OFF.format('OpenAI'), text, usage)      # checked after the loop: the usage comes last
    if finish == 'content_filter': raise LLMError('OpenAI withheld the reply (content filter)', text, usage)
    return (text,) + usage


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
    """Errors worth another try: a dropped connection, or an OpenAI API error (also one sent mid-stream)."""
    kinds = []
    for mod, name in (('openai', 'APIError'), ('httpx', 'TransportError')):
        try: kinds.append(getattr(importlib.import_module(mod), name))
        except ImportError: pass
    return tuple(kinds)


def generate_json(system, user, max_tokens=None, effort=DEFAULT_EFFORT, images=()):
    """Returns (parsed object, {'in': tokens, 'out': tokens, 'cost': USD}, raw text). Waits for a free slot.
    images: PNG bytes the model looks at (the visual review). A call that fails on a transient error is made up to twice
    more; every failure is raised as an LLMError with its usage."""
    bill = lambda t_in, t_out, billed_in: {'in': t_in, 'out': t_out, 'cost': cost(billed_in, t_out)}
    for attempt in range(3):
        try:
            with SLOT: text, *u = _openai(system, user, max_tokens or MODEL['max_out'], effort, images)
            break
        except LLMError as e:
            if e.usage: e.usage = bill(*e.usage)
            raise
        except _transient() as e:
            if attempt == 2: raise LLMError(f'OpenAI call failed: {type(e).__name__}: {e}') from e
    usage = bill(*u)
    try: return parse_json(text), usage, text
    except LLMError as e: e.usage = usage; raise


def generate_image(prompt):
    """One illustration from the image model (config.IMAGE_MODEL). Returns (PNG bytes, cost in USD)."""
    from openai import OpenAI
    try:
        r = OpenAI(api_key=secret('OPENAI_API_KEY'), max_retries=RETRIES).images.generate(
            model=IMAGE_MODEL['name'], prompt=prompt, size=IMAGE_MODEL['size'], quality=IMAGE_MODEL['quality'], n=1)
    except _transient() as e: raise LLMError(f'The image model failed: {type(e).__name__}: {e}') from e
    return base64.b64decode(r.data[0].b64_json), IMAGE_MODEL['price']


def embed(texts):
    """OpenAI embeddings for a list of texts (the library uses one fixed model). Returns a list of vectors."""
    from openai import OpenAI
    from config import EMBED_MODEL
    client, out = OpenAI(api_key=secret('OPENAI_API_KEY'), max_retries=RETRIES), []
    for i in range(0, len(texts), 100):
        out += [d.embedding for d in client.embeddings.create(model=EMBED_MODEL, input=[t[:8000] for t in texts[i:i + 100]]).data]
    return out
