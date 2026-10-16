"""Database (direct Postgres connection to Supabase) and file storage (Supabase Storage)."""
import functools, os
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from config import secret

BUCKETS = ('books', 'outputs')


@functools.cache
def _pool():
    # prepare_threshold=None: Supabase's pooler (transaction mode) does not support prepared statements
    return ConnectionPool(secret('DATABASE_URL'), min_size=1, max_size=8, open=True,
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


@functools.cache
def _storage():
    from supabase import create_client
    return create_client(secret('SUPABASE_URL'), secret('SUPABASE_KEY')).storage


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
