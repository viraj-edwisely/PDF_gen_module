-- Run automatically by db.init() on startup; every statement is safe to repeat.
create extension if not exists vector;

create table if not exists books (
  id bigserial primary key, title text not null, subject text not null, paper text,
  file_hash text unique not null, storage_path text, page_count int default 0, page_offset int default 0,
  status text not null default 'processing', error text, uploaded_by text, created_at timestamptz default now());

create table if not exists pages (                 -- raw text per PDF page (1-based index)
  book_id bigint references books on delete cascade, pdf_page int, text text, primary key (book_id, pdf_page));

create table if not exists units (                 -- printed page numbers
  id bigserial primary key, book_id bigint references books on delete cascade, name text, start_page int, end_page int);

create table if not exists chunks (                -- page numbers are PDF pages
  id bigserial primary key, book_id bigint references books on delete cascade,
  page_start int, page_end int, heading text, text text, embedding vector(1536),
  tsv tsvector generated always as (to_tsvector('english', text)) stored);
create index if not exists chunks_embedding on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_tsv on chunks using gin (tsv);
create index if not exists chunks_book_page on chunks (book_id, page_start);

create table if not exists runs (
  id bigserial primary key, mode text not null, book_id bigint references books on delete set null,
  scope_start int, scope_end int, provider text, model text, options jsonb default '{}',
  status text not null default 'queued', cost_usd numeric default 0, cost_cap numeric default 5,
  created_by text, created_at timestamptz default now(), heartbeat_at timestamptz);

create table if not exists run_topics (
  id bigserial primary key, run_id bigint references runs on delete cascade, name text, position int,
  status text not null default 'queued', step text, warnings jsonb default '[]', cost_usd numeric default 0,
  pdf_path text, json_path text, error text);

create table if not exists steps (                 -- saved output of each pipeline step: powers resume and cost totals
  run_topic_id bigint references run_topics on delete cascade, name text, output jsonb,
  input_tokens int default 0, output_tokens int default 0, cost_usd numeric default 0, primary key (run_topic_id, name));

-- the app connects with its own database credentials; nothing is readable through Supabase's public API
alter table books enable row level security;   alter table pages enable row level security;
alter table units enable row level security;   alter table chunks enable row level security;
alter table runs enable row level security;    alter table run_topics enable row level security;
alter table steps enable row level security;
