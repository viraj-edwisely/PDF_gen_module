#!/usr/bin/env python3
"""Every figure of a content JSON as a PNG, for the visual review: python figure_pngs.py content.json out_dir
Prints JSON: [{"path": [...], "file": "...png", "kind", "title", "caption"}] (figures that cannot be drawn are skipped:
the drawing check reports those). Run as a subprocess: matplotlib must not be shared between threads."""
import json, os, shutil, sys
import figures


def walk(x, path=()):
    if isinstance(x, dict):
        if 'kind' in x and 'spec' in x and not (x['kind'] == 'illustration' and not (x['spec'] or {}).get('file')):
            yield path, x
        for k, v in x.items():
            if k != 'spec': yield from walk(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from walk(v, path + (i,))


if __name__ == '__main__':
    content, out = json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2]
    os.makedirs(out, exist_ok=True)
    found = []
    for k, (path, f) in enumerate(walk(content)):
        try: png = figures.render(f['kind'], f['spec'])
        except Exception: continue
        dst = os.path.join(out, f'{k:03d}.png'); shutil.copy(png, dst)
        found.append({'path': list(path), 'file': dst, 'kind': f['kind'], 'title': f.get('title', ''), 'caption': f.get('caption', '')})
    print(json.dumps(found, ensure_ascii=False))
