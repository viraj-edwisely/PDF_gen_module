"""Database (direct Postgres connection to Supabase) and file storage (Supabase Storage)."""
import functools, json, os, re
from urllib.parse import quote, unquote
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from config import secret

BUCKETS = ('books', 'outputs')


def _dsn():
    """DATABASE_URL with the password encoded, so a password containing @ / # ? : still works."""
    scheme, rest = secret('DATABASE_URL').strip().split('://', 1)
    userinfo, host = rest.rsplit('@', 1)                       # the last @ separates the password from the host
    user, password = userinfo.split(':', 1)
    return f'{scheme}://{user}:{quote(unquote(password), safe="")}@{host}'


@functools.cache
def _pool():
    # prepare_threshold=None: Supabase's pooler (transaction mode) does not support prepared statements
    return ConnectionPool(_dsn(), min_size=1, max_size=12, open=True,
                          kwargs={'autocommit': True, 'row_factory': dict_row, 'prepare_threshold': None})


def sql(query, args=()):
    """Run one statement; returns the rows (a list of dicts) for SELECT and RETURNING, else []."""
    with _pool().connection() as conn:
        cur = conn.execute(query, args)
        return cur.fetchall() if cur.description else []


def many(query, rows):
    """Run one statement for many rows (bulk insert)."""
    with _pool().connection() as conn:
        conn.cursor().executemany(query, rows)


def event(email, action, run_id=None, cost=0, **detail):
    """Record one usage event for the Usage page (sign in, run started, model call, PDF ready, download...).
    Tracking never breaks a page or a run, so a failure here is ignored."""
    try: sql('insert into events (email, action, run_id, cost_usd, detail) values (%s,%s,%s,%s,%s::jsonb)', (email, action, run_id, cost, json.dumps(detail, default=str)))
    except Exception: pass


@functools.cache
def _storage():
    from supabase import create_client
    url = re.sub(r'/(rest|storage|auth)/v1.*$', '', secret('SUPABASE_URL').strip().rstrip('/'))   # accept the Data API address too
    return create_client(url, secret('SUPABASE_KEY').strip()).storage


def upload(bucket, path, data, content_type='application/octet-stream'):
    _storage().from_(bucket).upload(path, data, {'content-type': content_type, 'upsert': 'true'})


def download(bucket, path):
    return _storage().from_(bucket).download(path)


def remove(bucket, paths):
    if paths: _storage().from_(bucket).remove(paths)


@functools.cache
def init():
    """Create tables and buckets on first start (safe to repeat)."""
    sql(open(os.path.join(os.path.dirname(__file__), 'schema.sql'), encoding='utf-8').read())
    have = {b.name for b in _storage().list_buckets()}
    for b in BUCKETS:
        if b not in have: _storage().create_bucket(b, options={'public': False})
