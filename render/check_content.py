#!/usr/bin/env python3
"""Try to draw every figure and every piece of maths in a content JSON, exactly as the renderers will.
Prints the failures as JSON: [{"path": [...], "what": "figure" | "maths", "error": "..."}].

Usage: python check_content.py content.json     (run as a subprocess: matplotlib must not be shared between threads)"""
import json, re, sys
import figures
from render_common import math_img
import tex as TEX

MATH = re.compile(r'(?<!\\)\$(.+?)(?<!\\)\$', re.S)


def brief(e):
    """The informative line of an error (matplotlib puts the reason on the last line)."""
    lines = [x.strip() for x in str(e).splitlines() if x.strip()]
    return f'{type(e).__name__}: ' + (lines[-1] if lines else '')


def walk(x, path=(), key=None):
    if isinstance(x, dict):
        if x.get('type') == 'code': return                  # code is shown as typed: $ is not maths there
        if 'kind' in x and 'spec' in x:
            try: figures.render(x['kind'], x['spec'])
            except Exception as e: yield {'path': list(path), 'what': 'figure', 'error': brief(e)[:240]}
        for k, v in x.items():
            if k not in ('kind', 'spec'): yield from walk(v, path + (k,), k)
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from walk(v, path + (i,), key)
    elif isinstance(x, str):
        for tex in TEX.lines(x) if key == 'latex' else [' '.join(m.split()) for m in MATH.findall(x)]:      # as the renderer draws them
            try: math_img(tex, display=key == 'latex')
            except Exception as e:
                yield {'path': list(path), 'what': 'maths', 'error': f'cannot draw the maths "{tex[:80]}": {brief(e)[:160]}'}
                break


if __name__ == '__main__':
    print(json.dumps(list(walk(json.load(open(sys.argv[1], encoding='utf-8'))))))
