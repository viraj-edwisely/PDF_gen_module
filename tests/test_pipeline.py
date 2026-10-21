"""The whole GATE pipeline offline: a scripted model, an in-memory stand-in for the database and storage, the real tidy,
checks, repairs, revision step, visual review and renderer. python -m pytest tests"""
import json, os, re, sys
import pytest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import content as C, llm, pipeline, review

EX = json.load(open(os.path.join(os.path.dirname(HERE), 'render', 'example_gate.json'), encoding='utf-8'))
SECTIONS = [n['heading'] for n in EX['notes']][:4]


class FakeDB:
    """Just enough of db.py: steps are remembered, warnings collected, everything else accepted."""
    def __init__(self): self.steps, self.warnings, self.files, self.quality = {}, [], {}, None

    def sql(self, q, args=()):
        if q.startswith('select status, cost_usd'): return [{'status': 'running', 'capped': False}]
        if q.startswith('select output from steps'): return [{'output': self.steps[args[1]]}] if args[1] in self.steps else []
        if q.startswith('insert into steps'): self.steps[args[1]] = json.loads(args[2]); return []
        if 'warnings = warnings ||' in q: self.warnings.append(args[0]); return []
        if q.startswith('select warnings'): return [{'warnings': self.warnings}]
        if q.startswith('update run_topics set quality'): self.quality = json.loads(args[0]); return []
        if 'returning cost_usd' in q: return [{'cost_usd': 0, 'cost_cap': 5}]
        if q.startswith('select * from illustrations'): return []
        return []

    def upload(self, bucket, path, data, ctype=''): self.files[path] = data
    def event(self, *a, **k): pass


def reply_for(user):
    """The scripted model: a plan, notes with structured examples, questions, a revision page, a clean visual review."""
    if 'Plan the GATE topic PDF' in user:
        return {'subtitle': 'Topic guide', 'syllabus_line': 'CPU scheduling', 'objectives': ['Compute waiting times'], 'prerequisites': ['Processes'],
                'storyline': 'From what a scheduler does to each algorithm and how GATE compares them.',
                'coverage': [{'subtopic': 'FCFS', 'section': SECTIONS[1]}, {'subtopic': 'SJF', 'section': SECTIONS[2]}],
                'notation': [{'symbol': 'WT', 'meaning': 'waiting time', 'unit': 'ms', 'convention': 'WT = TAT - BT'}],
                'sections': [{'heading': h, 'ideas': 'x', 'example': 'y', 'figure': 'gantt: schedule -> waiting time', 'builds_on': ''} for h in SECTIONS],
                'archetypes': ['average waiting time']}
    if 'Write concept-note sections' in user:
        heads = re.findall(r'"heading": "([^"]+)"', user.split('Sections to write now')[1].split('Other sections')[0])
        return {'notes': [{'heading': h, 'blocks': [
            'Short intuition.', {'type': 'formula', 'key': True, 'latex': 'WT = TAT - BT', 'where': [['WT', 'waiting time', 'ms']]},
            {'type': 'example', 'title': 'Average waiting time', 'problem': 'P1 (0, 4), P2 (1, 3). Find the average WT under FCFS.',
             'given': [['P1', 'AT 0, BT 4'], ['P2', 'AT 1, BT 3']], 'find': 'average WT',
             'steps': [{'say': 'Schedule', 'latex': 'P1: 0-4,\\ P2: 4-7', 'blocks': [{'type': 'figure', 'kind': 'gantt', 'spec': {'segments': [['P1', 0, 4], ['P2', 4, 7]]}}]},
                       {'say': 'Waiting times', 'latex': 'WT_1 = 0,\\ WT_2 = 4 - 1 = 3'}, {'say': 'Average', 'latex': '(0 + 3)/2', 'result': '1.5 ms'}],
             'answer': '1.5 ms', 'rushed': 'Forgetting the arrival time gives 2 ms.', 'check': {'expr': '(0 + 3)/2', 'answer': '1.5'}},
            {'type': 'trap', 'text': 'Subtract the arrival time.'}]} for h in heads]}
    if 'Write all the questions' in user:
        as_steps = lambda qs: [{**{k: v for k, v in q.items() if k != 'solution'}, 'steps': [{'say': 'Work it out', 'result': str(q.get('solution'))[:80]}]} for q in qs]
        return {'practice': as_steps(EX['practice']), 'sample_paper': {**EX['sample_paper'], 'questions': as_steps(EX['sample_paper']['questions'])},
                'traps': EX['traps']}           # questions written the current way: the working as "steps", no "solution"
    if 'Write the revision page' in user:
        return {'rows': [{'section': h, 'idea': 'one line', 'formula': 'WT = TAT - BT', 'rule': 'r', 'trap': 't'} for h in SECTIONS], 'flow': ['A -> B']}
    if 'checking the figures' in user or 'checking the layout' in user: return {'issues': []}
    if 'reviewing a GATE topic PDF' in user: return {'issues': [], 'weak': []}
    return {}


@pytest.fixture
def fake(monkeypatch):
    f = FakeDB()
    for mod in (pipeline, review): monkeypatch.setattr(mod, 'db', f)
    calls = []
    def generate_json(system, user, max_tokens=None, effort=None, images=()):
        calls.append((user[:60], len(images)))
        out = reply_for(user)
        return out, {'in': 100, 'out': 100, 'cost': 0.0}, json.dumps(out)
    monkeypatch.setattr(llm, 'generate_json', generate_json)
    monkeypatch.setattr(pipeline.retrieve, 'topic_context', lambda *a, **k: {'text': '', 'found': False, 'whole_scope': False})
    f.calls = calls
    return f


def test_gate_pipeline_end_to_end(fake):
    run = {'id': 1, 'mode': 'gate', 'book_id': None, 'scope_start': None, 'scope_end': None, 'created_by': 'a@b.c',
           'options': {'paper': 'CS', 'subject': 'Operating Systems', 'subtopics': {'CPU scheduling': ['FCFS', 'SJF']}, 'verify': True, 'visual_review': True}}
    pipeline.process({'id': 7, 'name': 'CPU scheduling'}, run)
    content = fake.steps['content']
    assert content['topic_name'] == 'CPU scheduling' and content['subtopics'] == ['FCFS', 'SJF']
    assert len(content['notes']) == 4 and content['revision']['rows'] and content['notes'][0]['blocks'][2]['steps']
    assert any(n for _, n in fake.calls if n), 'the visual review sent images'
    assert fake.quality and fake.quality['examples_with_steps'] == 4 and fake.quality['subtopics_covered'] == 2
    assert any(p.endswith('.pdf') for p in fake.files), fake.warnings
    assert not [w for w in fake.warnings if 'left out' in w], fake.warnings          # questions solved in steps are kept
    assert len(content['practice']) == len(EX['practice']) and all(q['steps'] for q in content['practice'])
    assert not [w for w in fake.warnings if 'raw maths' in w or 'could not be drawn' in w], fake.warnings
    assert not fake.quality['sections_without_figure'] and not [w for w in fake.warnings if 'asks for a figure' in w]    # figures inside steps count
