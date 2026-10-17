"""Measure PDF quality on a fixed set of topics, so a prompt change can be judged by numbers instead of by eye.

    python tools/eval.py start [--writer OpenAI] [--check]   create one run per subject of tools/eval_topics.json;
                                                              the deployed app generates them (needs DATABASE_URL)
    python tools/eval.py score NAME                          score the finished PDFs: the app's own checks, counted,
                                                              and a judge model's rubric (needs ANTHROPIC_API_KEY)
    python tools/eval.py compare NAME_A NAME_B               average scores side by side

Results go to evals/NAME/ (runs.json, scores.json, report.md). Run from the app folder; the secrets come from
.streamlit/secrets.toml or the environment. A round of 8 PDFs costs what 8 runs cost, plus about $0.05 per PDF to judge."""
import argparse, datetime, json, os, statistics, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); os.chdir(HERE)
import content as C, db, jobs, llm, pipeline
from config import VERIFY_PROVIDER

CRITERIA = ('correctness', 'gate_fidelity', 'depth', 'examples', 'figures', 'questions')
OUT = os.path.join(HERE, 'evals')


def start(writer, check):
    name = datetime.datetime.now().strftime('%Y%m%d-%H%M') + f'-{writer}'
    runs = []
    for g in json.load(open(os.path.join(HERE, 'tools', 'eval_topics.json'), encoding='utf-8')):
        options = {'topics': g['topics'], 'paper': g['paper'], 'subject': g['subject'], 'syllabus_line': '', 'prompt': '', 'verify': check}
        runs.append(jobs.create_run('gate', None, (None, None), writer, options, 'eval'))
    os.makedirs(os.path.join(OUT, name), exist_ok=True)
    json.dump({'writer': writer, 'check': check, 'runs': runs}, open(os.path.join(OUT, name, 'runs.json'), 'w'))
    print(f'{name}: runs {runs} created. When the Runs page shows them finished: python tools/eval.py score {name}')


def code_metrics(c, warnings):
    """What the app's own checks say about a finished PDF (the problems it would send back, counted)."""
    probs = [m for i, n in enumerate(c['notes']) for j, b in enumerate(n['blocks'])
             for _, m, _ in (C.example_problems(b, ()) if b.get('type') == 'example' else C.figure_problems(b, ()) if b.get('type') == 'figure' else [])]
    probs += [m for k in ('practice',) for i, q in enumerate(c.get(k, [])) for _, m, _ in C.question_checks(q, (k, i))]
    probs += [m for i, q in enumerate(c['sample_paper']['questions']) for _, m, _ in C.question_checks(q, ('sample_paper', 'questions', i))]
    blocks = [b for n in c['notes'] for b in C.walk_blocks(n['blocks'])]
    return {'sections': len(c['notes']), 'n_examples': sum(b.get('type') == 'example' for b in blocks),
            'n_figures': sum(b.get('type') == 'figure' for b in blocks), 'pyqs': len(c.get('pyqs', [])),
            'flagged': len(probs), 'notes_on_pdf': len(warnings or []), 'flags': probs[:12]}


def brief(c):
    """The content as the judge reads it: figures as short descriptions, not their full drawing specs."""
    def walk(x):
        if isinstance(x, dict):
            return pipeline.figure_brief(x) if x.get('type') == 'figure' or ('kind' in x and 'spec' in x) else {k: walk(v) for k, v in x.items()}
        return [walk(v) for v in x] if isinstance(x, list) else x
    return walk({k: c.get(k) for k in ('topic_name', 'notes', 'traps', 'revision_card', 'pyqs', 'practice', 'sample_paper')})


def score(name):
    meta = json.load(open(os.path.join(OUT, name, 'runs.json')))
    rows = []
    for rt in db.sql("select t.*, r.options from run_topics t join runs r on r.id = t.run_id where t.run_id = any(%s) order by t.run_id, t.position", (meta['runs'],)):
        if not rt['json_path']: rows.append({'topic': rt['name'], 'status': rt['status'], 'error': (rt['error'] or '')[:200]}); continue
        c = json.loads(db.download('outputs', rt['json_path']))
        o = rt['options']
        prompt = pipeline.fill(pipeline.read('eval_judge.md'), TOPIC=rt['name'], PAPER=o['paper'], SUBJECT=o['subject'],
                               CONTENT=json.dumps(brief(c), ensure_ascii=False))
        judged, usage, _ = llm.generate_json(VERIFY_PROVIDER, 'You review study material. Reply with the JSON object only.', prompt)
        rows.append({'topic': rt['name'], 'status': rt['status'], 'cost': float(rt['cost_usd']), 'judge_cost': usage['cost'],
                     **code_metrics(c, rt['warnings']), 'scores': judged.get('scores', {}), 'worst': judged.get('worst', []), 'best': judged.get('best', '')})
        print(f"scored {rt['name']}: {judged.get('scores')}")
    json.dump(rows, open(os.path.join(OUT, name, 'scores.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(OUT, name, 'report.md'), 'w', encoding='utf-8').write(report(name, meta, rows))
    print(report(name, meta, rows))


def averages(rows):
    done = [r for r in rows if r.get('scores')]
    avg = {k: round(statistics.mean(float(r['scores'].get(k, 0)) for r in done), 2) for k in CRITERIA} if done else {}
    for k in ('flagged', 'notes_on_pdf', 'n_examples', 'n_figures', 'cost'):
        if done: avg[k] = round(statistics.mean(r[k] for r in done), 2)
    avg['made'] = f'{len(done)} of {len(rows)}'
    return avg


def report(name, meta, rows):
    lines = [f"# Evaluation {name}", f"Writer {meta['writer']}, second check {'on' if meta['check'] else 'off'}.", '',
             '| Topic | ' + ' | '.join(CRITERIA) + ' | flagged | notes | cost |', '|' + '---|' * (len(CRITERIA) + 4)]
    for r in rows:
        if not r.get('scores'): lines.append(f"| {r['topic']} | not made: {r.get('status')} {r.get('error', '')} |"); continue
        lines.append(f"| {r['topic']} | " + ' | '.join(str(r['scores'].get(k, '')) for k in CRITERIA) + f" | {r['flagged']} | {r['notes_on_pdf']} | ${r['cost']:.2f} |")
    lines += ['', '**Averages:** ' + ', '.join(f'{k} {v}' for k, v in averages(rows).items()), '', '## Weakest points']
    lines += [f"- **{r['topic']}**: {w}" for r in rows for w in r.get('worst', [])]
    return '\n'.join(lines) + '\n'


def compare(a, b):
    load = lambda n: averages(json.load(open(os.path.join(OUT, n, 'scores.json'), encoding='utf-8')))
    A, B = load(a), load(b)
    print(f'{"":14} {a:>22} {b:>22}')
    for k in A:
        print(f'{k:14} {str(A[k]):>22} {str(B.get(k, "")):>22}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('start'); s.add_argument('--writer', default='OpenAI'); s.add_argument('--check', action='store_true')
    sub.add_parser('score').add_argument('name')
    c = sub.add_parser('compare'); c.add_argument('a'); c.add_argument('b')
    a = ap.parse_args()
    start(a.writer, a.check) if a.cmd == 'start' else score(a.name) if a.cmd == 'score' else compare(a.a, a.b)
