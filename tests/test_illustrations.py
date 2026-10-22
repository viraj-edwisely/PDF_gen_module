"""The illustration library: what the writer is told, which pictures a PDF may use, drawing on demand, and the app's own numbered markers.
python -m pytest tests"""
import io, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), 'render')]
import pytest
from PIL import Image
import figures, llm, marks, review

PARTS = ['Piston', 'Inlet valve', 'Spark plug']
MARKS = [{'x': 0.5, 'y': 0.8}, {'x': 0.3, 'y': 0.2}, {'x': 0.7, 'y': 0.2}]


def png(size=(600, 400)):
    out = io.BytesIO(); Image.new('RGB', size, 'white').save(out, 'PNG'); return out.getvalue()


class FakeDB:
    def __init__(self, rows=()):
        self.rows = {r['concept']: dict(r) for r in rows}; self.files = {}
    def sql(self, q, args=()):
        if q.startswith('select concept, title, parts'): return [r for r in self.rows.values() if r['status'] in ('approved', 'pending')]
        if q.startswith('select * from illustrations'): return [self.rows[args[0]]] if args[0] in self.rows else []
        if q.startswith('insert into illustrations'):
            k, title, desc, parts, mk, path, status, review_, by = args
            import json
            self.rows[k] = {'concept': k, 'title': title, 'description': desc, 'parts': json.loads(parts), 'marks': json.loads(mk), 'path': path, 'status': status, 'review': review_}
        return []
    def upload(self, bucket, path, data, ctype=''): self.files[path] = data
    def download(self, bucket, path): return self.files[path]


class Job:
    system, effort, run = 'system', 'low', {'created_by': 'a@b.c'}
    def __init__(self): self.warnings, self.charged = [], 0
    def warn(self, t): self.warnings.append(t)
    def charge(self, usage, name): self.charged += usage['cost']


def row(k, status, marks=MARKS):
    return {'concept': k, 'title': k.title(), 'description': '', 'parts': PARTS, 'marks': marks, 'path': k + '.png', 'status': status, 'review': 'ok'}


def content(*concepts):
    return {'notes': [{'blocks': [{'type': 'figure', 'kind': 'illustration', 'spec': {'concept': c, 'title': c, 'description': 'a cut-away', 'parts': PARTS}} for c in concepts]}]}


@pytest.fixture
def library(monkeypatch):
    def make(*rows):
        f = FakeDB(rows); f.files.update({r['path']: png() for r in rows}); monkeypatch.setattr(review, 'db', f); return f
    return make


def test_writer_is_told_what_the_library_holds(library):
    library(row('engine', 'approved'), row('pump', 'pending'), row('lathe', 'rejected'))
    on, off = review.brief(True), review.brief(False)
    assert 'engine' in on and 'pump' in on and 'lathe' not in on and '1. Piston' in on          # approved and waiting pictures are usable, rejected ones are not
    assert 'NEW pictures' in on and 'not allowed' in off and 'NEW pictures' not in off


def test_a_pdf_uses_approved_and_waiting_pictures_and_leaves_out_the_rest(library):
    library(row('engine', 'approved'), row('pump', 'pending'), row('lathe', 'rejected'))
    job, c = Job(), content('engine', 'pump', 'lathe', 'missing')
    c, folder = review.illustrations(job, c, False)
    figs = [b['spec'] for b in c['notes'][0]['blocks']]
    assert [f['concept'] for f in figs] == ['engine', 'pump'] and not figs[0]['unreviewed'] and figs[1]['unreviewed']
    assert figs[0]['marks'] == MARKS and os.path.exists(figs[0]['file'])
    assert any('Unreviewed' in w for w in job.warnings) and any('rejected' in w for w in job.warnings) and any('not in the library' in w for w in job.warnings)


def test_a_new_concept_is_drawn_and_used_at_once_when_allowed(library, monkeypatch):
    f = library()
    monkeypatch.setattr(llm, 'generate_image', lambda text: (png(), 0.05))
    monkeypatch.setattr(llm, 'generate_json', lambda *a, **k: ({'ok': True, 'problem': '', 'marks': MARKS}, {'in': 10, 'out': 10, 'cost': 0.001}, ''))
    job = Job()
    c, folder = review.illustrations(job, content('engine'), True)
    spec = c['notes'][0]['blocks'][0]['spec']
    assert f.rows['engine']['status'] == 'pending' and f.rows['engine']['marks'] == MARKS and spec['unreviewed'] and spec['marks'] == MARKS
    assert job.charged == pytest.approx(0.051) and not any('rejected' in w for w in job.warnings)
    _, none = review.illustrations(Job(), content('pump'), False)                                      # not allowed: nothing is drawn
    assert 'pump' not in f.rows


def test_a_picture_that_fails_its_check_twice_is_rejected_and_left_out(library, monkeypatch):
    f = library()
    calls = []
    monkeypatch.setattr(llm, 'generate_image', lambda text: (calls.append(text) or png(), 0.05))
    monkeypatch.setattr(llm, 'generate_json', lambda *a, **k: ({'ok': False, 'problem': 'the piston is missing', 'marks': [None, None, None]}, {'in': 1, 'out': 1, 'cost': 0}, ''))
    job = Job()
    c, folder = review.illustrations(job, content('engine'), True)
    assert len(calls) == 2 and 'the piston is missing' in calls[1]                                   # one more try, told what was wrong
    assert f.rows['engine']['status'] == 'rejected' and c['notes'][0]['blocks'] == []


def test_the_picture_prompt_asks_for_no_text_at_all():
    p = review.prompt({'title': 'Engine', 'description': 'cut-away', 'parts': PARTS})
    assert 'No words, letters, numbers' in p and 'Piston; Inlet valve; Spark plug' in p and 'callout' not in p


def test_markers_are_cleaned_and_drawn_where_the_parts_are():
    assert marks.clean([{'x': 0.5, 'y': 0.5}, {'x': 2, 'y': 0.1}, None, 'bad'], 5) == [{'x': 0.5, 'y': 0.5}, None, None, None, None]
    im = marks.mark_parts(Image.new('RGB', (600, 400), 'white'), [{'x': 0.5, 'y': 0.5}, None])
    assert im.getpixel((309, 200)) == marks.PURPLE and im.getpixel((20, 20)) == (255, 255, 255, 255)        # a purple circle at the part, nothing elsewhere


def test_an_illustration_with_markers_and_the_tag_draws(tmp_path):
    f = tmp_path / 'engine.png'; f.write_bytes(png())
    out = figures.render('illustration', {'concept': 'engine', 'title': 'Engine', 'parts': PARTS, 'marks': MARKS, 'file': str(f), 'unreviewed': True})
    assert os.path.getsize(out) > 5000
