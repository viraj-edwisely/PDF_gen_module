"""Build a GATE PDF that holds every formula style and every figure kind, to look at after a renderer change:
    python tests/stress_pdf.py stress.pdf"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(os.path.dirname(HERE), 'render')
sys.path[:0] = [HERE, RENDER]
import figures
from stress_data import AWKWARD, FORMULAS

out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'stress.pdf')
maths = [{'type': 'formula', 'latex': t} for t in FORMULAS]
maths += [{'type': 'para', 'text': 'In a sentence: ' + ', '.join(f'${t}$' for t in FORMULAS[:12]) + '.'},
          {'type': 'table', 'header': ['Formula', 'Drawn in a cell'], 'rows': [[f'`{t[:40]}`', f'${t}$'] for t in FORMULAS[:10]]}]
figs = [b for name, (kind, spec) in figures.GALLERY.items() for b in ({'type': 'subhead', 'text': name}, {'type': 'figure', 'kind': kind, 'spec': spec})]
figs += [b for title, kind, spec in AWKWARD for b in ({'type': 'subhead', 'text': title}, {'type': 'figure', 'kind': kind, 'spec': spec, 'width': 0.9})]
content = json.load(open(os.path.join(RENDER, 'example_gate.json'), encoding='utf-8'))
content['notes'] = [{'heading': 'Maths', 'blocks': maths}, {'heading': 'Figures', 'blocks': figs}]
src = os.path.join(tempfile.mkdtemp(), 'stress.json')
json.dump(content, open(src, 'w', encoding='utf-8'))
r = subprocess.run([sys.executable, os.path.join(RENDER, 'render_gate.py'), src, out], capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1] if r.returncode == 0 else r.stderr[-800:])
