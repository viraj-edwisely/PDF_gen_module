#!/usr/bin/env python3
"""Try to draw every figure and every piece of maths in a content JSON, exactly as the renderers will.
Prints the failures as JSON: [{"path": [...], "what": "figure" | "maths" | "layout", "error": "..."}]
(layout: the figure draws, but labels still overlap).

Usage: python check_content.py content.json     (run as a subprocess: matplotlib must not be shared between threads)"""
import json, re, sys
import figures
from render_common import math_img, math_split
import tex as TEX


def brief(e):
    """The informative line of an error (matplotlib puts the reason on the last line)."""
    lines = [x.strip() for x in str(e).splitlines() if x.strip()]
    return f'{type(e).__name__}: ' + (lines[-1] if lines else '')


def _labels(x):
    """Every label text in a figure spec."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ('label', 'text', 'to_label') and isinstance(v, str): yield v
            else: yield from _labels(v)
    elif isinstance(x, list):
        for v in x: yield from _labels(v)


EQUIPMENT = re.compile(r'\b(column|reboiler|condenser|still|reactor|drum|exchanger|evaporator|boiler|decanter|absorber|stripper|separator|'
                       r'tank|pump|heater|cooler|compressor|turbine|vessel|furnace)\b', re.I)


def misuse(kind, spec):
    """A figure that draws but is the wrong figure: process equipment drawn as a signal chain, a sketch drawn as a graph,
    a graph with nothing on one axis, or labels so long they cannot sit clear of the drawing. Returns the reason, or ''."""
    if kind == 'block' and isinstance(spec, dict):
        found = [m.group(0) for t in _labels(spec) if (m := EQUIPMENT.search(t))]
        if found: return (f'"{found[0]}" is process equipment, and a block diagram is a signal or control chain (its arrows are signals, not streams): '
                          'draw this process with the process kind (the equipment on a grid, the streams as labelled arrows)')
    if kind not in ('plot', 'geometry', 'process') or not isinstance(spec, dict): return ''
    if kind == 'plot' and not spec.get('panels'):
        if 'schematic' in f"{spec.get('xlabel', '')} {spec.get('ylabel', '')}".lower():
            return ('this is a sketch drawn as a graph (its axes are "schematic"): draw it as geometry (no axes) with '
                    'segments, points and dim items for the lengths')
        ys = [y for c in spec.get('curves', []) for y in (c.get('y') or [] if 'x' in c else [None])] + [p.get('y') for p in spec.get('points', [])]
        if ys and None not in ys and len({round(float(y), 9) for y in ys}) == 1:
            return 'everything lies on one horizontal line, so the y axis says nothing: draw it as geometry with dim items'
    long = [t for t in _labels(spec) if len(TEX.plain(t).replace('$', '')) > 30]
    if long: return (f'label "{long[0][:40]}" is too long to sit clear of the drawing: use a symbol, a value or 1 to 4 words '
                     'and say the rest in the caption')
    return ''


def walk(x, path=(), key=None):
    if isinstance(x, dict):
        if x.get('type') == 'code': return                  # code is shown as typed: $ is not maths there
        if 'kind' in x and 'spec' in x and (why := misuse(x['kind'], x['spec'])):
            yield {'path': list(path), 'what': 'layout', 'error': why}
        elif 'kind' in x and 'spec' in x and not (x['kind'] == 'illustration' and not (x['spec'] or {}).get('file')):    # illustrations come from the library later
            try: n = figures.overlaps(figures.render(x['kind'], x['spec']))
            except Exception as e: yield {'path': list(path), 'what': 'figure', 'error': brief(e)[:240]}
            else:
                if n: yield {'path': list(path), 'what': 'layout', 'error': f'{n} label(s) in this figure still overlap other labels or '
                             'run off the plot: shorten the labels, label fewer points, or spread them out'}
        for k, v in x.items():
            if k not in ('kind', 'spec'): yield from walk(v, path + (k,), k)
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from walk(v, path + (i,), key)
    elif isinstance(x, str):
        for tex in TEX.lines(x) if key == 'latex' else [' '.join(m.split()) for m in math_split(x)[1::2]]:      # as the renderer draws them
            try: math_img(tex, display=key == 'latex')
            except Exception as e:
                yield {'path': list(path), 'what': 'maths', 'error': f'cannot draw the maths "{tex[:80]}": {brief(e)[:160]}'}
                break


if __name__ == '__main__':
    print(json.dumps(list(walk(json.load(open(sys.argv[1], encoding='utf-8'))))))
