"""One call for all providers: generate_json(provider, system, user) -> (object, usage).

Providers are asked for a single JSON object; we parse and validate it ourselves (the pipeline's checks and repair loop),
because the providers' schema dialects do not fit our content JSON. The SDKs retry rate limits and 5xx errors themselves.
"""
import json, re
from config import PROVIDERS, cost, secret


class LLMError(Exception):
    pass


def _claude(model, system, user, max_tokens):
    import anthropic
    with anthropic.Anthropic(api_key=secret('ANTHROPIC_API_KEY')).messages.stream(
            model=model, max_tokens=max_tokens, system=system, messages=[{'role': 'user', 'content': user}],
            output_config={'effort': 'medium'}) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason in ('max_tokens', 'refusal'): raise LLMError(f'Claude stopped early: {msg.stop_reason}')
    u = msg.usage
    return ''.join(b.text for b in msg.content if b.type == 'text'), (u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0), u.output_tokens)


def _openai(model, system, user, max_tokens):
    from openai import OpenAI
    text, usage = '', (0, 0)
    for ev in OpenAI(api_key=secret('OPENAI_API_KEY')).chat.completions.create(
            model=model, max_completion_tokens=max_tokens, stream=True, stream_options={'include_usage': True},
            response_format={'type': 'json_object'}, messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]):
        if ev.choices:
            text += ev.choices[0].delta.content or ''
            if ev.choices[0].finish_reason == 'length': raise LLMError('OpenAI output was cut off (token limit)')
        if ev.usage: usage = (ev.usage.prompt_tokens, ev.usage.completion_tokens)
    return text, usage


def _gemini_client():
    """Gemini through Vertex AI, signed in with the service-account JSON (no API key)."""
    from google import genai
    from google.oauth2 import service_account
    info = secret('GOOGLE_SERVICE_ACCOUNT_JSON')
    info = json.loads(info) if isinstance(info, str) else dict(info)     # pasted as a JSON string or as a TOML table
    creds = service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/cloud-platform'])
    args = dict(project=info['project_id'], location=secret('GOOGLE_CLOUD_LOCATION') or 'global', credentials=creds)
    try: return genai.Client(enterprise=True, **args)      # google-genai 2.x
    except TypeError: return genai.Client(vertexai=True, **args)    # google-genai 1.x


def _gemini(model, system, user, max_tokens):
    from google import genai
    text, usage = '', (0, 0)
    cfg = genai.types.GenerateContentConfig(system_instruction=system, response_mime_type='application/json', max_output_tokens=max_tokens)
    for ch in _gemini_client().models.generate_content_stream(model=model, contents=user, config=cfg):
        text += ch.text or ''
        if ch.candidates and str(ch.candidates[0].finish_reason).endswith('MAX_TOKENS'): raise LLMError('Gemini output was cut off (token limit)')
        if ch.usage_metadata:
            m = ch.usage_metadata; usage = (m.prompt_token_count or 0, (m.candidates_token_count or 0) + (m.thoughts_token_count or 0))
    return text, usage


CALLS = {'Claude': _claude, 'OpenAI': _openai, 'Gemini': _gemini}


def parse_json(text):
    """Pull the JSON object out of a reply, tolerating code fences and a sentence before or after it."""
    text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    a, b = text.find('{'), text.rfind('}')
    if a < 0 or b < a: raise LLMError('the model did not return a JSON object')
    try: return json.loads(text[a:b + 1])
    except json.JSONDecodeError as e: raise LLMError(f'the model returned invalid JSON: {e}')


def generate_json(provider, system, user, max_tokens=32000):
    """Returns (parsed object, {'in': tokens, 'out': tokens, 'cost': USD})."""
    text, (t_in, t_out) = CALLS[provider](PROVIDERS[provider]['model'], system, user, max_tokens)
    return parse_json(text), {'in': t_in, 'out': t_out, 'cost': cost(provider, t_in, t_out)}


def embed(texts):
    """OpenAI embeddings for a list of texts (the library uses one fixed model). Returns a list of vectors."""
    from openai import OpenAI
    from config import EMBED_MODEL
    client, out = OpenAI(api_key=secret('OPENAI_API_KEY')), []
    for i in range(0, len(texts), 100):
        out += [d.embedding for d in client.embeddings.create(model=EMBED_MODEL, input=[t[:8000] for t in texts[i:i + 100]]).data]
    return out
