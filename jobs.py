"""Background workers: create, cancel and resume runs; process queued topics and uploaded books."""
import contextlib, json, threading, time
import db, ingest, pipeline
from config import COST_CAP, MODEL, STALE_SECONDS, TOPIC_PARALLEL, WORKERS

# next queued topic; at most TOPIC_PARALLEL topics of one run are processed at the same time
CLAIM = """update run_topics set status='running', step='Starting' where id = (
             select t.id from run_topics t join runs r on r.id = t.run_id
             where t.status='queued' and r.status in ('queued', 'running')
               and (select count(*) from run_topics x where x.run_id = t.run_id and x.status = 'running') < %s
             order by t.run_id, t.position limit 1 for update of t skip locked) returning *"""
CLAIM_BOOK = """update books set status='processing', step='Starting', progress=0 where id = (
                  select id from books where status='queued' order by created_at limit 1 for update skip locked) returning *"""
# a finished run says whether its PDFs failed: done / partial (some failed) / failed (none made)
FINISH = """update runs set status = case
              when not exists (select 1 from run_topics where run_id=%(id)s and status in ('done', 'warnings')) then 'failed'
              when exists (select 1 from run_topics where run_id=%(id)s and status in ('failed', 'stopped')) then 'partial'
              else 'done' end
            where id=%(id)s and status='running'
              and not exists (select 1 from run_topics where run_id=%(id)s and status in ('queued', 'running'))"""


def create_run(mode, book_id, scope, options, user):
    """One run_topic per topic for GATE; a single module for Non-GATE. Returns the run id."""
    topics = options['topics']
    names = topics if mode == 'gate' else [f"{options['subject']} module: " + ', '.join(topics[:3]) + ('...' if len(topics) > 3 else '')]
    title = ', '.join(topics[:3]) + (f' +{len(topics) - 3} more' if len(topics) > 3 else '')
    run = db.sql('insert into runs (mode, title, book_id, scope_start, scope_end, provider, model, options, cost_cap, created_by) values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s) returning id',
                 (mode, title, book_id, scope[0], scope[1], 'OpenAI', MODEL['name'], json.dumps(options), COST_CAP, user))[0]['id']
    db.many('insert into run_topics (run_id, name, position) values (%s,%s,%s)', [(run, n, i) for i, n in enumerate(names)])
    pipeline.log(run, None, f'Run created by {user}: {len(names)} PDF(s), writer {MODEL["name"]}, thinking {options.get("effort")}')
    db.event(user, 'run started', run, title=title, type='GATE' if mode == 'gate' else 'Non-GATE', pdfs=len(names), writer=MODEL['name'], thinking=options.get('effort'), book=bool(book_id))
    return run


def cancel_run(run_id):
    pipeline.log(run_id, None, 'Cancel requested')
    db.sql("update runs set status='cancelled' where id=%s and status in ('queued', 'running')", (run_id,))
    db.sql("update run_topics set status='stopped', error='cancelled' where run_id=%s and status='queued'", (run_id,))


def resume_run(run_id):
    """Re-queue unfinished topics (interrupted, stopped or failed). A run that hit its cap gets another cap's worth of budget."""
    pipeline.log(run_id, None, 'Resume requested')
    db.sql("update run_topics set status='queued', error=null where run_id=%s and status in ('running', 'stopped', 'failed')", (run_id,))
    db.sql("update runs set status='queued', cost_cap = greatest(cost_cap, cost_usd + %s), heartbeat_at=now() where id=%s", (COST_CAP, run_id))


def _stop(run_id, rt_id, run_status, reason):
    db.sql("update run_topics set status='stopped', error=%s where id=%s", (reason, rt_id))
    db.sql("update run_topics set status='stopped', error=%s where run_id=%s and status='queued'", (reason, run_id))
    db.sql('update runs set status=%s where id=%s', (run_status, run_id))


@contextlib.contextmanager
def _heartbeat(run_id):
    """Keeps runs.heartbeat_at fresh during long model calls, so only a dead worker looks 'interrupted'."""
    stop = threading.Event()
    def beat():
        while not stop.wait(10):
            try: db.sql('update runs set heartbeat_at=now() where id=%s', (run_id,))
            except Exception: pass          # a database hiccup must not end the heartbeat (the run would look interrupted)
    threading.Thread(target=beat, daemon=True).start()
    try: yield
    finally: stop.set()


def _topic(rt):
    run = db.sql('select * from runs where id=%s', (rt['run_id'],))[0]
    db.sql("update runs set status='running', heartbeat_at=now() where id=%s and status='queued'", (run['id'],))
    pipeline.log(run['id'], rt['id'], 'Started')
    with _heartbeat(run['id']):
        try: pipeline.process(rt, run); pipeline.log(run['id'], rt['id'], 'Finished')
        except pipeline.CapReached: _stop(run['id'], rt['id'], 'stopped', 'stopped: cost cap reached'); pipeline.log(run['id'], rt['id'], 'Stopped: cost cap reached')
        except pipeline.Cancelled: _stop(run['id'], rt['id'], 'cancelled', 'cancelled'); pipeline.log(run['id'], rt['id'], 'Cancelled')
        except Exception as e:
            err = f'{type(e).__name__}: {e}'.replace('\x00', '')      # the database refuses NUL characters
            try:
                db.sql("update run_topics set status='failed', error=%s where id=%s", (err[:1000], rt['id']))
                pipeline.log(run['id'], rt['id'], f'FAILED: {err}')
                db.event(run['created_by'], 'pdf failed', run['id'], topic=rt['name'], error=err[:200])
            except Exception:       # a database hiccup: one more try, so the topic does not stay 'running'
                time.sleep(5); db.sql("update run_topics set status='failed', error=%s where id=%s", (err[:1000], rt['id']))
    db.sql(FINISH, {'id': run['id']})


def _book(b):
    def progress(frac, msg): db.sql('update books set progress=%s, step=%s where id=%s', (frac, msg, b['id']))
    try: data = db.download('books', b['storage_path'])
    except Exception as e:
        db.sql("update books set status='failed', error=%s where id=%s", (f'the uploaded file could not be read from storage: {e}'[:500], b['id'])); return
    try: ingest.ingest(b['id'], data, progress)
    except Exception: pass                  # ingest() records the error on the book


def _work_loop():
    while True:
        try:
            claimed = db.sql(CLAIM, (TOPIC_PARALLEL,))
            if claimed: _topic(claimed[0]); continue
            book = db.sql(CLAIM_BOOK)
            if book: _book(book[0]); continue
            time.sleep(3)
        except Exception:
            time.sleep(10)    # database hiccup: try again


def start_workers():
    """Start the worker threads (once per app process). Work whose worker died (app restart or sleep) is queued again."""
    stale = "status='running' and heartbeat_at < now() - make_interval(secs => %s)"
    db.sql(f"update run_topics set status='queued' where status='running' and run_id in (select id from runs where {stale})", (STALE_SECONDS,))
    db.sql(f"update runs set status='queued' where {stale}", (STALE_SECONDS,))
    db.sql("update books set status='queued' where status='processing'")      # a book being processed when the app stopped starts again
    for _ in range(WORKERS): threading.Thread(target=_work_loop, daemon=True).start()
