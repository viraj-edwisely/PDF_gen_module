"""Runs and background workers: create a run, claim queued topics, run the pipeline, cancel, resume."""
import contextlib, json, threading, time
import db, pipeline
from config import COST_CAP, PROVIDERS, STALE_SECONDS, WORKERS

# next queued topic whose run has no other topic running (topics of one run go one after another)
CLAIM = """update run_topics set status='running', step='Starting' where id = (
             select t.id from run_topics t join runs r on r.id = t.run_id
             where t.status='queued' and r.status in ('queued', 'running')
               and not exists (select 1 from run_topics x where x.run_id = t.run_id and x.status = 'running')
             order by t.run_id, t.position limit 1 for update of t skip locked) returning *"""


def create_run(mode, book_id, scope, provider, options, user):
    """One run_topic per topic for GATE; a single module for Non-GATE. Returns the run id."""
    names = options['topics'] if mode == 'gate' else [f"{options['subject']} module: " + ', '.join(options['topics'][:3]) + ('...' if len(options['topics']) > 3 else '')]
    run = db.sql('insert into runs (mode, book_id, scope_start, scope_end, provider, model, options, cost_cap, created_by) values (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s) returning id',
                 (mode, book_id, scope[0], scope[1], provider, PROVIDERS[provider]['model'], json.dumps(options), COST_CAP, user))[0]['id']
    db.many('insert into run_topics (run_id, name, position) values (%s,%s,%s)', [(run, n, i) for i, n in enumerate(names)])
    return run


def cancel_run(run_id):
    db.sql("update runs set status='cancelled' where id=%s and status in ('queued', 'running')", (run_id,))
    db.sql("update run_topics set status='stopped', error='cancelled' where run_id=%s and status='queued'", (run_id,))


def resume_run(run_id):
    """Re-queue unfinished topics (interrupted, stopped or failed). A run that hit its cap gets another cap's worth of budget."""
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
        while not stop.wait(10): db.sql('update runs set heartbeat_at=now() where id=%s', (run_id,))
    threading.Thread(target=beat, daemon=True).start()
    try: yield
    finally: stop.set()


def _work_loop():
    while True:
        try:
            claimed = db.sql(CLAIM)
            if not claimed: time.sleep(3); continue
            rt = claimed[0]
            run = db.sql('select * from runs where id=%s', (rt['run_id'],))[0]
            db.sql("update runs set status='running', heartbeat_at=now() where id=%s and status='queued'", (run['id'],))
            with _heartbeat(run['id']):
                try: pipeline.process(rt, run)
                except pipeline.CapReached: _stop(run['id'], rt['id'], 'stopped', 'stopped: cost cap reached')
                except pipeline.Cancelled: _stop(run['id'], rt['id'], 'cancelled', 'cancelled')
                except Exception as e: db.sql("update run_topics set status='failed', error=%s where id=%s", (f'{type(e).__name__}: {e}'[:500], rt['id']))
            if not db.sql("select 1 from run_topics where run_id=%s and status in ('queued', 'running')", (run['id'],)):
                db.sql("update runs set status='done' where id=%s and status='running'", (run['id'],))
        except Exception:
            time.sleep(10)    # database hiccup: try again


def start_workers():
    """Start the worker threads (once per app process). Work whose worker died (app restart or sleep) is queued again."""
    stale = "status='running' and heartbeat_at < now() - make_interval(secs => %s)"
    db.sql(f"update run_topics set status='queued' where status='running' and run_id in (select id from runs where {stale})", (STALE_SECONDS,))
    db.sql(f"update runs set status='queued' where {stale}", (STALE_SECONDS,))
    for _ in range(WORKERS): threading.Thread(target=_work_loop, daemon=True).start()
