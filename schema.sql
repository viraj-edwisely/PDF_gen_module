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
drop index if exists chunks_embedding;   -- an HNSW index scans the whole library before the book filter and returned too few chunks; one book is small enough for an exact scan
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

create table if not exists logs (                  -- what happened during a run, shown on the Runs page
  id bigserial primary key, run_id bigint references runs on delete cascade, run_topic_id bigint references run_topics on delete cascade,
  at timestamptz default now(), text text);
create index if not exists logs_run on logs (run_id, id);

create table if not exists users (                 -- people who may sign in, managed on the Admin page; passwords only as scrypt hashes
  email text primary key, name text, password_hash text not null, is_admin boolean default false, active boolean default true,
  created_by text, created_at timestamptz default now(), last_login timestamptz);

create table if not exists events (                -- usage per person (Usage page); no foreign keys, so it keeps its rows when runs or books are deleted
  id bigserial primary key, at timestamptz default now(), email text, action text, run_id bigint, cost_usd numeric default 0, detail jsonb default '{}');
create index if not exists events_at on events (at);

-- added after the first release (safe to repeat); before the carry-over below, which reads runs.title
alter table runs add column if not exists title text;                          -- the topic names, for the run list
alter table books add column if not exists progress real default 0;            -- background processing of uploads
alter table books add column if not exists step text;
alter table run_topics add column if not exists quality jsonb;                -- the quality report of the finished PDF (Runs page)

create table if not exists feedback (               -- what reviewers marked on a PDF: by category and page, the source of new checks and tests
  id bigserial primary key, run_topic_id bigint references run_topics on delete cascade, email text,
  category text, page int, comment text not null, created_at timestamptz default now());
create index if not exists feedback_topic on feedback (run_topic_id);

create table if not exists illustrations (          -- the library of approved illustrations, one per concept, reused by every PDF
  concept text primary key, title text, description text, parts jsonb default '[]', path text,
  status text not null default 'pending',          -- pending (waits for a person), approved, rejected
  review text, created_by text, created_at timestamptz default now(), reviewed_by text, reviewed_at timestamptz);

do $$ begin
  if not exists (select 1 from events) then        -- first start with usage tracking: carry over the existing runs
    insert into events (at, email, action, run_id, detail)
      select created_at, created_by, 'run started', id, jsonb_build_object('title', title, 'writer', provider) from runs;
    insert into events (at, email, action, run_id, cost_usd, detail)
      select created_at, created_by, 'model call', id, cost_usd, jsonb_build_object('step', 'all calls of the run (before usage tracking)', 'provider', provider) from runs where cost_usd > 0;
    insert into events (at, email, action, run_id, detail)
      select r.created_at, r.created_by, case when t.pdf_path is null then 'pdf failed' else 'pdf ready' end, r.id, jsonb_build_object('topic', t.name)
      from run_topics t join runs r on r.id = t.run_id where t.pdf_path is not null or t.status = 'failed';
  end if;
end $$;

-- the app connects with its own database credentials; nothing is readable through Supabase's public API
alter table books enable row level security;   alter table pages enable row level security;
alter table units enable row level security;   alter table chunks enable row level security;
alter table runs enable row level security;    alter table run_topics enable row level security;
alter table steps enable row level security;   alter table logs enable row level security;
alter table events enable row level security;  alter table users enable row level security;
alter table feedback enable row level security; alter table illustrations enable row level security;
