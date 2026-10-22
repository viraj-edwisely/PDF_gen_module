"""The quality report of a finished GATE PDF: what it covers and how, counted from its content JSON and the warnings of
the renderer and the checks. Shown on the Runs page; the numbers SMEs and the eval round compare between versions."""
import re
from content import walk_blocks, _key
from check_gate_level import key_formulas

COMPUTED = {'beam', 'mohr', 'pressure', 'waveform', 'spectrum', 'cycle', 'control', 'mccabe', 'vle'}


def _words(t): return len(re.sub(r'\$[^$]*\$', 'x', str(t or '')).split())


def report(content, warnings, pages):
    """A flat dict of counts (JSON-ready)."""
    notes = content.get('notes', [])
    blocks = [list(walk_blocks(n.get('blocks', []))) for n in notes]
    figs = [b for bl in blocks for b in bl if b.get('type') == 'figure']
    examples = [b for bl in blocks for b in bl if b.get('type') == 'example']
    formulas = [b for bl in blocks for b in bl if b.get('type') == 'formula']
    qs = content.get('practice', []) + (content.get('sample_paper') or {}).get('questions', [])
    kinds = {}
    for f in figs: kinds[f.get('kind', '?')] = kinds.get(f.get('kind', '?'), 0) + 1
    subs = content.get('subtopics') or []
    covered = {_key(c.get('subtopic')) for c in content.get('coverage') or []}
    words = [sum(_words(b.get('text')) for b in bl if b.get('type') == 'para') for bl in blocks]
    w = ' '.join(warnings)
    return {
        'pages': pages, 'sections': len(notes),
        'subtopics': len(subs), 'subtopics_covered': sum(_key(s) in covered for s in subs) if 'coverage' in content else None,     # older PDFs: unknown
        'prose_words_per_section': round(sum(words) / len(words)) if words else 0, 'longest_section_words': max(words, default=0),
        'worked_examples': len(examples), 'examples_with_steps': sum(bool(b.get('steps')) for b in examples),
        'figures': len(figs), 'computed_figures': sum(v for k, v in kinds.items() if k in COMPUTED), 'figure_kinds': kinds,
        'sections_without_figure': [n.get('heading') for n, bl in zip(notes, blocks) if not any(b.get('type') == 'figure' for b in bl)],
        'key_formulas': sum(bool(b.get('key')) for b in formulas), 'formulas_with_symbols': sum(bool(b.get('where')) for b in formulas),
        'formula_sheet': sum(len(key_formulas(n)) for n in notes),
        'questions': len(qs), 'questions_with_steps': sum(bool(q.get('steps')) for q in qs), 'pyqs': len(content.get('pyqs') or []),
        'revision_rows': len((content.get('revision') or {}).get('rows') or []),
        'raw_maths_on_page': int(m.group(1)) if (m := re.search(r'(\d+) place\(s\) show raw maths', w)) else 0,
        'mostly_empty_pages': len(re.findall(r'Page \d+ is only', w)),
        'figures_left_out': len(re.findall(r'could not be drawn and was left out', w)),
        'notes_to_review': len(warnings),
    }


LABELS = {'pages': 'Pages', 'sections': 'Sections', 'subtopics_covered': 'Subtopics covered', 'prose_words_per_section': 'Prose words per section',
          'worked_examples': 'Worked examples', 'examples_with_steps': '… with steps', 'figures': 'Figures', 'computed_figures': '… computed from physics',
          'key_formulas': 'Key formulas', 'formulas_with_symbols': 'Formulas with symbol lists', 'questions': 'Questions',
          'questions_with_steps': '… with step solutions', 'revision_rows': 'Revision rows', 'raw_maths_on_page': 'Raw maths on a page',
          'mostly_empty_pages': 'Mostly empty pages', 'figures_left_out': 'Figures left out', 'notes_to_review': 'Notes to review'}


def rows(q):
    """The report as (label, value) rows for display; subtopics as "covered of listed"."""
    out = []
    for k, label in LABELS.items():
        if k not in q: continue
        v = f"{q['subtopics_covered']} of {q['subtopics']}" if k == 'subtopics_covered' else q[k]
        if k == 'subtopics_covered' and (not q.get('subtopics') or q[k] is None): continue
        out.append((label, v))
    if q.get('sections_without_figure'): out.append(('Sections without a figure', ', '.join(q['sections_without_figure'])))
    return out
