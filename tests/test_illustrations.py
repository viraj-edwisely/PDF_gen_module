"""The illustration library: what the writer is told, which pictures a PDF may use, and drawing on demand (one image call, no check, no redraw).
python -m pytest tests"""
import io, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), 'render')]
import pytest
from PIL import Image
import figures, llm, review

PARTS = ['Piston', 'Inlet valve', 'Spark plug']


def png(size=(600, 400)):
    out = io.BytesIO(); Image.new('RGB', size, 'white').save(out, 'PNG'); return out.getvalue()


class FakeDB:
    def __init__(self, rows=()):
        self.rows = {r['concept']: dict(r) for r in rows}; self.files = {}
    def sql(self, q, args=()):
        if q.startswith('select concept, title, parts'): return [r for r in self.rows.values() if r['status'] in ('approved', 'pending')]
        if q.startswith('select * from illustrations'): return [self.rows[args[0]]] if args[0] in self.rows else []
        if q.startswith('insert into illustrations'):
            k, title, desc, parts, path, by = args
            import json
            self.rows[k] = {'concept': k, 'title': title, 'description': desc, 'parts': json.loads(parts), 'path': path, 'status': 'pending', 'review': ''}
        return []
    def upload(self, bucket, path, data, ctype=''): self.files[path] = data
    def download(self, bucket, path): return self.files[path]


class Job:
    system, effort, run = 'system', 'low', {'created_by': 'a@b.c'}
    def __init__(self): self.warnings, self.charged = [], 0
    def warn(self, t): self.warnings.append(t)
    def charge(self, usage, name): self.charged += usage['cost']


def row(k, status):
    return {'concept': k, 'title': k.title(), 'description': '', 'parts': PARTS, 'path': k + '.png', 'status': status, 'review': 'ok'}


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
    assert [f['concept'] for f in figs] == ['engine', 'pump']
    assert os.path.exists(figs[0]['file']) and figs[0]['parts'] == PARTS
    assert any('waiting for approval' in w for w in job.warnings) and any('rejected' in w for w in job.warnings) and any('not in the library' in w for w in job.warnings)


def test_a_new_concept_is_drawn_once_without_a_check_and_used_at_once_when_allowed(library, monkeypatch):
    f = library()
    drawn = []
    monkeypatch.setattr(llm, 'generate_image', lambda text: (drawn.append(text) or png(), 0.02))
    monkeypatch.setattr(llm, 'generate_json', lambda *a, **k: pytest.fail('a picture is not checked by a model'))
    job = Job()
    c, folder = review.illustrations(job, content('engine'), True)
    spec = c['notes'][0]['blocks'][0]['spec']
    assert len(drawn) == 1 and f.rows['engine']['status'] == 'pending' and 'unreviewed' not in spec and os.path.exists(spec['file'])
    assert job.charged == pytest.approx(0.02)
    _, none = review.illustrations(Job(), content('pump'), False)                                      # not allowed: nothing is drawn
    assert 'pump' not in f.rows and len(drawn) == 1


def test_a_stored_picture_is_at_most_1024_pixels_wide(library, monkeypatch):
    f = library()
    monkeypatch.setattr(llm, 'generate_image', lambda text: (png((1536, 1024)), 0.02))
    review.illustrations(Job(), content('engine'), True)
    assert Image.open(io.BytesIO(f.files['engine.png'])).width == 1024


def test_the_picture_prompt_asks_for_numbered_parts_and_no_other_text():
    p = review.prompt({'title': 'Engine', 'description': 'cut-away', 'parts': PARTS})
    assert '1. Piston; 2. Inlet valve; 3. Spark plug' in p and 'only text' in p


def test_an_illustration_draws(tmp_path):
    f = tmp_path / 'engine.png'; f.write_bytes(png())
    out = figures.render('illustration', {'concept': 'engine', 'title': 'Engine', 'parts': PARTS, 'file': str(f)})
    assert os.path.getsize(out) > 5000
