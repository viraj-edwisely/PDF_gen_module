#!/usr/bin/env python3
"""Draw every figure in a content JSON and print the ones that fail as JSON: [{"path": [...], "error": "..."}].

Usage: python check_figures.py content.json     (run as a subprocess: matplotlib must not be shared between threads)"""
import json, sys
import figures


def walk(x, path=()):
    if isinstance(x, dict):
        if 'kind' in x and 'spec' in x:
            try: figures.render(x['kind'], x['spec'])
            except Exception as e: yield {'path': list(path), 'error': f'{type(e).__name__}: {e}'[:200]}
        for k, v in x.items(): yield from walk(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from walk(v, path + (i,))


if __name__ == '__main__':
    print(json.dumps(list(walk(json.load(open(sys.argv[1], encoding='utf-8'))))))
