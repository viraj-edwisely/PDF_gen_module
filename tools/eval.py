"""Measure PDF quality on the golden topic set, so a prompt change is judged by numbers instead of by eye.

    python tools/eval.py start [--review] [--effort medium]   create one GATE run per topic of tools/eval_topics.json;
                                                               the deployed app generates them (needs DATABASE_URL)
    python tools/eval.py score NAME                           score the finished PDFs: the quality report and the app's
                                                               checks, counted, and a judge's rubric (the writer model)
    python tools/eval.py compare NAME_A NAME_B                averages side by side; a change ships only if no criterion drops

Results go to evals/NAME/ (runs.json, scores.json, report.md). Run from the app folder; the secrets come from
.streamlit/secrets.toml or the environment. A round costs what its 12 runs cost, plus a few cents per PDF to judge."""
import argparse, datetime, json, os, statistics, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); os.chdir(HERE)
import content as C, db, jobs, llm, pipeline

CRITERIA = ('correctness', 'coverage', 'simplicity', 'depth', 'structure', 'examples', 'figures', 'revision', 'questions')
MEASURES = ('pages', 'subtopics_covered', 'prose_words_per_section', 'examples_with_steps', 'figures', 'computed_figures', 'raw_maths_on_page',
            'mostly_empty_pages', 'figures_left_out', 'notes_to_review')
OUT = os.path.join(HERE, 'evals')


def start(review, effort):
    name = datetime.datetime.now().strftime('%Y%m%d-%H%M') + ('-review' if review else '')
    runs = []
    for g in json.load(open(os.path.join(HERE, 'tools', 'eval_topics.json'), encoding='utf-8')):
        options = {'topics': [g['topic']], 'subtopics': {g['topic']: g['subtopics']}, 'paper': g['paper'], 'subject': g['subject'],
                   'syllabus_line': '', 'prompt': '', 'verify': True, 'visual_review': review, 'effort': effort}
        runs.append(jobs.create_run('gate', None, (None, None), options, 'eval'))
    os.makedirs(os.path.join(OUT, name), exist_ok=True)
    json.dump({'review': review, 'effort': effort, 'runs': runs}, open(os.path.join(OUT, name, 'runs.json'), 'w'))
    print(f'{name}: runs {runs} created. When the Runs page shows them finished: python tools/eval.py score {name}')


def flags(c):
    """The problems the app's own checks would still send back on the finished content, counted."""
    probs = [m for i, n in enumerate(c['notes']) for j, b in enumerate(n['blocks'])
             for _, m, _ in (C.example_problems(b, ()) if b.get('type') == 'example' else C.figure_problems(b, ()) if b.get('type') == 'figure' else [])]
    probs += [m for i, n in enumerate(c['notes']) for _, m, _ in C.writing_problems(n, ('notes', i))]
    probs += [m for k in ('practice',) for i, q in enumerate(c.get(k, [])) for _, m, _ in C.question_checks(q, (k, i))]
    probs += [m for i, q in enumerate(c['sample_paper']['questions']) for _, m, _ in C.question_checks(q, ('sample_paper', 'questions', i))]
    return probs


def brief(c):
    """The content as the judge reads it: figures as short descriptions, not their full drawing specs."""
    def walk(x):
        if isinstance(x, dict):
            return pipeline.figure_brief(x) if x.get('type') == 'figure' or ('kind' in x and 'spec' in x) else {k: walk(v) for k, v in x.items()}
        return [walk(v) for v in x] if isinstance(x, list) else x
    return walk({k: c.get(k) for k in ('topic_name', 'subtopics', 'notes', 'traps', 'revision', 'pyqs', 'practice', 'sample_paper')})


def score(name):
    meta = json.load(open(os.path.join(OUT, name, 'runs.json')))
    rows = []
    for rt in db.sql("select t.*, r.options from run_topics t join runs r on r.id = t.run_id where t.run_id = any(%s) order by t.run_id, t.position", (meta['runs'],)):
        if not rt['json_path']: rows.append({'topic': rt['name'], 'status': rt['status'], 'error': (rt['error'] or '')[:200]}); continue
        c = json.loads(db.download('outputs', rt['json_path']))
        o = rt['options']
        prompt = pipeline.fill(pipeline.read('eval_judge.md'), TOPIC=rt['name'], PAPER=o['paper'], SUBJECT=o['subject'],
                               SUBTOPICS='; '.join(c.get('subtopics') or []) or '(none listed)', CONTENT=json.dumps(brief(c), ensure_ascii=False))
        judged, usage, _ = llm.generate_json('You review GATE study material as a subject expert. Reply with the JSON object only.', prompt, 16_000, 'high')
        f = flags(c)
        rows.append({'topic': rt['name'], 'status': rt['status'], 'cost': float(rt['cost_usd']), 'judge_cost': usage['cost'],
                     'quality': {k: (rt['quality'] or {}).get(k) for k in MEASURES}, 'flagged': len(f), 'flags': f[:12],
                     'scores': judged.get('scores', {}), 'worst': judged.get('worst', []), 'best': judged.get('best', '')})
        print(f"scored {rt['name']}: {judged.get('scores')}")
    json.dump(rows, open(os.path.join(OUT, name, 'scores.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(OUT, name, 'report.md'), 'w', encoding='utf-8').write(report(name, meta, rows))
    print(report(name, meta, rows))


def averages(rows):
    done = [r for r in rows if r.get('scores')]
    avg = {k: round(statistics.mean(float(r['scores'].get(k, 0) or 0) for r in done), 2) for k in CRITERIA} if done else {}
    for k in ('pages', 'prose_words_per_section', 'figures', 'computed_figures', 'raw_maths_on_page', 'mostly_empty_pages', 'figures_left_out'):
        vals = [r['quality'][k] for r in done if isinstance(r['quality'].get(k), (int, float))]
        if vals: avg[k] = round(statistics.mean(vals), 2)
    for k in ('flagged', 'cost'):
        if done: avg[k] = round(statistics.mean(r[k] for r in done), 2)
    avg['made'] = f'{len(done)} of {len(rows)}'
    return avg


def report(name, meta, rows):
    lines = [f"# Evaluation {name}", f"Thinking {meta.get('effort')}, visual review {'on' if meta.get('review') else 'off'}.", '',
             '| Topic | ' + ' | '.join(CRITERIA) + ' | pages | flagged | cost |', '|' + '---|' * (len(CRITERIA) + 4)]
    for r in rows:
        if not r.get('scores'): lines.append(f"| {r['topic']} | not made: {r.get('status')} {r.get('error', '')} |"); continue
        lines.append(f"| {r['topic']} | " + ' | '.join(str(r['scores'].get(k, '')) for k in CRITERIA) + f" | {r['quality'].get('pages')} | {r['flagged']} | ${r['cost']:.2f} |")
    lines += ['', '**Averages:** ' + ', '.join(f'{k} {v}' for k, v in averages(rows).items()), '', '## Weakest points']
    lines += [f"- **{r['topic']}**: {w}" for r in rows for w in r.get('worst', [])]
    return '\n'.join(lines) + '\n'


def compare(a, b):
    """Averages side by side, and the criteria that got worse (a change ships only when none did)."""
    load = lambda n: averages(json.load(open(os.path.join(OUT, n, 'scores.json'), encoding='utf-8')))
    A, B = load(a), load(b)
    print(f'{"":26} {a:>22} {b:>22}')
    for k in A: print(f'{k:26} {str(A[k]):>22} {str(B.get(k, "")):>22}')
    worse = [k for k in CRITERIA if k in A and k in B and B[k] < A[k] - 0.1]
    print('\nWorse in ' + b + ': ' + (', '.join(worse) if worse else 'nothing'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('start'); s.add_argument('--review', action='store_true'); s.add_argument('--effort', default='medium')
    sub.add_parser('score').add_argument('name')
    c = sub.add_parser('compare'); c.add_argument('a'); c.add_argument('b')
    a = ap.parse_args()
    start(a.review, a.effort) if a.cmd == 'start' else score(a.name) if a.cmd == 'score' else compare(a.a, a.b)
