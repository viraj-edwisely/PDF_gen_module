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
        if q.startswith('select json_path'): return [{'json_path': self.json_path}]
        return []

    def upload(self, bucket, path, data, ctype=''): self.files[path] = data
    def download(self, bucket, path): return self.files[path]
    def event(self, *a, **k): pass


def reply_for(user):
    """The scripted model: a plan, notes with structured examples, questions, a revision page, a clean visual review."""
    if 'Plan the GATE topic PDF' in user:
        if 'their own images' in user:          # the user's images: U1 goes in the second section, U2 fits nowhere
            plan = reply_for(user.replace('their own images', ''))
            plan['sections'][1]['photos'] = ['U1', 'U9']
            return {**plan, 'photos_unused': [{'id': 'U2', 'reason': 'it shows a different topic'}]}
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
    if 'A finished PDF has to be changed' in user:
        return {'summary': 'Reworded the first intuition.', 'fixes': [{'ref': 'notes/0/blocks/0', 'value': {'type': 'para', 'text': 'Changed intuition.'}}, {'ref': 'notes/99/blocks/0', 'value': 'x'}]}
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


def test_a_requested_change_rewrites_only_what_was_asked_in_one_call(fake):
    run = {'id': 1, 'mode': 'gate', 'book_id': None, 'scope_start': None, 'scope_end': None, 'created_by': 'a@b.c',
           'options': {'paper': 'CS', 'subject': 'Operating Systems', 'subtopics': {'CPU scheduling': ['FCFS', 'SJF']}, 'verify': True, 'visual_review': False}}
    pipeline.process({'id': 7, 'name': 'CPU scheduling'}, run)
    before = json.loads(fake.files['1/7.json'])
    fake.json_path, fake.steps, fake.warnings, n = '1/7.json', {}, [], len(fake.calls)
    pipeline.process({'id': 8, 'name': 'CPU scheduling'}, {**run, 'id': 2, 'options': {**run['options'], 'edit': {'from': 7, 'request': 'reword the first intuition'}}})
    after = json.loads(fake.files['2/8.json'])
    assert len(fake.calls) == n + 1                                                       # one call: no plan, notes, questions or review
    assert after['notes'][0]['blocks'][0] == {'type': 'para', 'text': 'Changed intuition.'}
    assert after['notes'][1:] == before['notes'][1:] and after['practice'] == before['practice'] and after['notes'][0]['blocks'][1:] == before['notes'][0]['blocks'][1:]
    assert any(w.startswith('Changed: Section') for w in fake.warnings) and any('notes/99/blocks/0' in w and 'not applied' in w for w in fake.warnings)


def jpeg(color):
    import io
    from PIL import Image
    out = io.BytesIO(); Image.new('RGB', (800, 500), color).save(out, 'JPEG'); return out.getvalue()


def test_the_users_images_are_placed_by_the_planner_and_drawn_in_the_pdf(fake):
    fake.files.update({'images/a.jpg': jpeg('red'), 'images/b.jpg': jpeg('blue')})
    images = [{'id': 'U1', 'name': 'gantt_board.jpg', 'hint': 'a Gantt chart on a board', 'path': 'images/a.jpg'},
              {'id': 'U2', 'name': 'turbine.jpg', 'hint': '', 'path': 'images/b.jpg'}]
    run = {'id': 1, 'mode': 'gate', 'book_id': None, 'scope_start': None, 'scope_end': None, 'created_by': 'a@b.c',
           'options': {'paper': 'CS', 'subject': 'Operating Systems', 'subtopics': {'CPU scheduling': ['FCFS', 'SJF']}, 'verify': True, 'visual_review': True,
                       'images': {'CPU scheduling': images}}}
    pipeline.process({'id': 7, 'name': 'CPU scheduling'}, run)
    plan_call = next(c for c in fake.calls if c[0].startswith('Plan the GATE'))
    assert plan_call[1] == 2                                                                 # the planner sees both images
    assert sorted(n for u, n in fake.calls if u.startswith('Write concept-note')) == [0, 1]  # only the notes call of its section sees U1
    content = json.loads(fake.files['1/7.json'])
    photos = [(i, b) for i, n in enumerate(content['notes']) for b in C.walk_blocks(n['blocks']) if b.get('kind') == 'photo']
    assert [(i, b['spec']['id'], b['spec']['path']) for i, b in photos] == [(1, 'U1', 'images/a.jpg')]     # the writer left it out: put in by code
    assert content['notes'][1]['blocks'][1]['kind'] == 'photo'                                # after the section's first paragraph
    assert any('"turbine.jpg" was left out: it shows a different topic' in w for w in fake.warnings), fake.warnings
    assert not [w for w in fake.warnings if 'could not be' in w or 'drawn' in w], fake.warnings
    pipeline.process({'id': 7, 'name': 'CPU scheduling'}, run)                                # resumed: the notes are not repeated
    assert sum('turbine.jpg' in w for w in fake.warnings) == 1


def test_each_image_stays_once_in_its_own_section():
    photos = {'U1': {'path': 'p1', 'hint': 'h1'}, 'U2': {'path': 'p2', 'hint': ''}}
    plan = {'sections': [{'heading': 'A', 'photos': ['U1', 'U1', 'U7']}, {'heading': 'B', 'photos': ['U1', 'U2']}, {'heading': 'C', 'photos': []}]}
    assert C.plan_photos(plan, ['U1', 'U2', 'U3']) == ['U3'] and [s['photos'] for s in plan['sections']] == [['U1'], ['U2'], []]
    fig = lambda i: {'type': 'figure', 'kind': 'photo', 'spec': {'id': i}}
    out = {'notes': [{'heading': 'A', 'blocks': [{'type': 'para', 'text': 'x'}, {'type': 'example', 'problem': [fig('U1')], 'steps': [{'blocks': [fig('U1')]}]}]},
                     {'heading': 'B', 'blocks': [fig('U1'), {'type': 'para', 'text': 'y'}]}, {'heading': 'C', 'blocks': []}]}
    C.place_photos(out, plan['sections'], photos)
    a, b, c = (n['blocks'] for n in out['notes'])
    assert a[1]['problem'] == [{**fig('U1'), 'spec': {'id': 'U1', 'path': 'p1'}}] and a[1]['steps'][0]['blocks'] == []     # kept once, where the writer put it
    assert [x.get('kind') for x in b] == [None, 'photo'] and b[1]['spec'] == {'id': 'U2', 'path': 'p2'}                    # U1 removed, U2 added after the paragraph
    assert c == []                                                                       # a missing section is left for the repair


def test_an_uploaded_image_is_shrunk_and_stored_as_jpeg(monkeypatch):
    import io
    from PIL import Image
    import jobs
    stored = {}
    monkeypatch.setattr(jobs.db, 'upload', lambda bucket, path, data, ctype='': stored.update({path: data}))
    src = io.BytesIO(); Image.new('RGBA', (4000, 1000), (0, 0, 0, 0)).save(src, 'PNG')
    path = jobs.save_image(src.getvalue())
    im = Image.open(io.BytesIO(stored[path]))
    assert path.startswith('images/') and path.endswith('.jpg') and im.format == 'JPEG' and im.size == (1600, 400)
    assert im.getpixel((10, 10)) == (255, 255, 255)                                         # transparent becomes white, not black
    assert jobs.save_image(src.getvalue()) == path                                           # the same image, the same file
