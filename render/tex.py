"""LaTeX as the writers produce it, rewritten into what matplotlib's mathtext can draw. Pure Python: used by the renderer
and by the content checks, so a formula that can be rewritten here is never sent back to the model."""
import re

FIXES = {r'\land': r'\wedge', r'\lor': r'\vee', r'\lnot': r'\neg', r'\implies': r'\Rightarrow', r'\iff': r'\Leftrightarrow', r'\le': r'\leq',
         r'\ge': r'\geq', r'\ne': r'\neq', r'\tfrac': r'\frac', r'\cfrac': r'\dfrac', r'\dbinom': r'\binom', r'\tbinom': r'\binom',
         r'\text': r'\mathrm', r'\textrm': r'\mathrm', r'\operatorname': r'\mathrm', r'\textbf': r'\mathbf', r'\bm': r'\mathbf', r'\boldsymbol': r'\mathbf',
         r'\emph': r'\mathit', r'\textit': r'\mathit', r'\dots': r'\ldots', r'\lVert': r'\Vert', r'\rVert': r'\Vert', r'\gets': r'\leftarrow',
         r'\lt': '<', r'\gt': '>', r'\square': '□', r'\Box': '□', r'\&': '&', r'\coloneqq': ':=', r'\eqqcolon': '=:', r'\stackrel': r'\overset',
         r'\bmod': r'\ \mathrm{mod}\ ', r'\pmod': r'\ \mathrm{mod}\ ', r'\displaystyle': '', r'\textstyle': '', r'\scriptstyle': '',
         r'\limits': '', r'\nolimits': '', r'\nonumber': '', r'\notag': '', r'\mod': r'\ \mathrm{mod}\ ', r'\lvert': '|', r'\rvert': '|',
         r'\R': r'\mathbb{R}', r'\N': r'\mathbb{N}', r'\Z': r'\mathbb{Z}', r'\Q': r'\mathbb{Q}', r'\C': r'\mathbb{C}', r'\hline': ''}
FIXES.update({rf'\{b}{s}': '' for b in ('big', 'Big', 'bigg', 'Bigg') for s in ('', 'l', 'r', 'm')})      # sized brackets: the bracket alone
ARG = r'\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}'          # one {...} argument, up to three levels of braces
ENV = re.compile(r'\\begin\{(\w+)\*?\}((?:(?!\\begin\{).)*?)\\end\{\1\*?\}', re.S)     # innermost environment first
BRACKETS = {'pmatrix': ('(', ')'), 'bmatrix': ('[', ']'), 'vmatrix': ('|', '|'), 'Vmatrix': (r'\Vert ', r'\Vert '), 'Bmatrix': (r'\{', r'\}')}
ROWS_ENVS = ('align', 'aligned', 'gather', 'gathered', 'split', 'eqnarray', 'multline', 'flalign', 'alignat')


def _rows(body):
    return [[c.strip() for c in re.split(r'(?<!\\)&', r)] for r in re.split(r'\\\\(?:\[[^\]]*\])?', body) if r.strip()]


def _cond(c):
    return re.sub(r'^\\(?:text|mathrm)\{\s*(?:if|for)\s*\}\s*|^(?:if|for)\s+', '', c)


def _env(m):
    name, body = m.group(1), m.group(2)
    if name in ('array', 'alignat', 'tabular'): body = re.sub(r'^\s*\{[^{}]*\}', '', body)        # the column spec {cc} or the count {2}
    rows = _rows(body)
    if name in ('cases', 'dcases', 'rcases'):
        return r'\{\ ' + r';\ \ '.join(r[0] + (r'\ \ \mathrm{if}\ ' + _cond(r[1]) if len(r) > 1 and r[1] else '') for r in rows)
    if name.endswith('matrix') or name in ('array', 'smallmatrix'):
        o, c = BRACKETS.get(name, ('[', ']'))
        return o + r';\ '.join(r'\ \ '.join(r) for r in rows) + c
    return r'\quad '.join(' '.join(r) for r in rows)


def normalize(tex):
    """One formula, rewritten for mathtext: unsupported environments, decorations and spellings become drawable ones."""
    t = re.sub(r'\\\\(?=[A-Za-z]{2})', r'\\', tex)            # \\text: a command over-escaped in the JSON, not a line break
    t = re.sub(r'(?<!\\)([_^])\s*([-+][\w.\\]+|\d+(?:\.\d+)?|[A-Za-z]{2,})', r'\1{\2}', t)    # ^-3, ^-j\omega, ^10, _max: the whole run raised
    t = re.sub(r'\\(?:tag|label)\*?' + ARG, '', t)
    t = re.sub(r'\\(?:boxed|cancel|bcancel|xcancel|phantom|hphantom|vphantom)' + ARG, r'\1', t)
    t = re.sub(r'\\(?:under|over)brace' + ARG + r'(?:\s*[_^]\s*(?:' + ARG + r'|\w))?', r'\1', t)
    t = re.sub(r'\\x(right|left)arrow(?:\[[^\]]*\])?' + ARG, r'\\overset{\2}{\\\1arrow}', t)
    t = re.sub(r'\\substack' + ARG, lambda m: m.group(1).replace('\\\\', ','), t)
    t = re.sub(r'\{([^{}]*)\\choose([^{}]*)\}', r'\\binom{\1}{\2}', t)
    t = re.sub(r'\\frac\s*(\d)\s*(\d)', r'\\frac{\1}{\2}', t)
    while ENV.search(t): t = ENV.sub(_env, t)
    t = re.sub(r'(?<!\\)&', r'\\ ', re.sub(r'\\\\(?:\[[^\]]*\])?', r';\\ ', t))      # stray row and column marks (\& is a literal &)
    t = re.sub(r'\\(?:text)?color\{[^{}]*\}', '', re.sub(r'(?<!\\)%', r'\\%', t))     # mathtext has no colours; a bare % is a TeX comment
    t = re.sub(r'\\[A-Za-z]+', lambda m: FIXES.get(m.group(0), m.group(0)), t)
    return re.sub(r'\\mathrm\{([^{}]*)\}', lambda m: '\\mathrm{' + re.sub(r'(?<!\\) ', lambda _: '\\ ', m.group(1)) + '}', t)     # mathtext drops spaces inside \mathrm


def display(tex):
    """A display formula: normalized, and every fraction outside a superscript or subscript drawn full size (\\dfrac), so
    numerator and denominator read at the size of the text around them."""
    t, out, script = normalize(tex), [], []           # script: for each open brace, whether it opened a ^{...} or _{...}
    i = 0
    while i < len(t):
        if t.startswith('\\frac', i) and not any(script) and not t[i + 5:i + 6].isalpha():
            out.append('\\dfrac'); i += 5; continue
        c = t[i]
        if c == '\\' and i + 1 < len(t): out.append(t[i:i + 2]); i += 2; continue
        if c == '{': script.append(bool(out) and out[-1] in ('^', '_'))
        elif c == '}' and script: script.pop()
        out.append(c); i += 1
    return ''.join(out)


SUP = str.maketrans('0123456789-+', '⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺')
UNIT = r'(?:mm|cm|km|m|s|kg|g|N|kN|MN|Pa|kPa|MPa|GPa|J|kJ|MJ|W|kW|MW|Hz|rad|K|A|V|Ω|mol|L)'


SUBSCRIPT = r'(?:\{[^{}$]+\}|[A-Za-z0-9]|[a-z]{2,4})'            # the subscript of a variable typed as text: _0, _i, _{max}, _min


def plain(text):
    """Running text as written by a model, made printable before its $...$ maths is drawn: units and powers that sit
    outside maths become characters (m$^3$ -> m³, mm^4 -> mm⁴, 10^6 -> 10⁶, kg/m3 -> kg/m³, N.m -> N·m), and a power with
    letters (e^-jwt) becomes maths. Maths between $...$ is left as it is."""
    t = re.sub(r'(?<=[A-Za-zΩ°)\]])\$\s*\^\s*\{?\s*([-+]?\d+)\s*\}?\s*\$', lambda m: m.group(1).translate(SUP), text)   # mm$^2$, s$^{-1}$
    t = re.sub(r'\$\s*\\(?:mathrm|text)\{\s*([A-Za-zΩ/·.\s]+?)\s*\}\s*\^\s*\{?\s*([-+]?\d+)\s*\}?\s*\$',
               lambda m: m.group(1).strip() + m.group(2).translate(SUP), t)                                     # $\mathrm{m}^3$
    parts = re.split(r'((?<!\\)\$.+?(?<!\\)\$)', t)
    for k in range(0, len(parts), 2):                       # outside maths only
        p = parts[k]
        p = re.sub(r'[Σ∑]_\{?(\w)=(\w+)\}?\^\{?(\w+)\}?', r'$\\sum_{\1=\2}^{\3}$', p)                                  # Σ_i=1^n typed as text
        p = re.sub(rf'(?<![\w$\\])[A-Za-z]_{SUBSCRIPT}(?:[A-Za-z]_{SUBSCRIPT})*(?:\^(?:\{{[^{{}}$]+\}}|[A-Za-z0-9]+))?(?![A-Za-z0-9_])',
                   lambda m: '$' + re.sub(r'([_^])([a-z]{2,4})(?![A-Za-z_])', r'\1{\2}', m.group(0)) + '$', p)                                # W_0, N_min, x_iK_i, P_i^sat
        p = re.sub(r'(?<=[\w)\]])(?:\^|\*\*)\{?([-+]?\d+)\}?(?!\w|\.\d)', lambda m: m.group(1).translate(SUP), p)    # mm^4, 10^6, x**2
        p = re.sub(r'(?<![\w$\\])([A-Za-z])\^\{?([-+]?[A-Za-z][\w]*)\}?', r'$\1^{\2}$', p)                      # e^-jwt, 2^n stays below
        p = re.sub(r'(?<=\d)\^\{?([A-Za-z]\w*)\}?', r'$^{\1}$', p)                                              # 2^n
        p = re.sub(r'(?<![\\$])\b(\w+)\^\{([^{}$]+)\}', r'$\1^{\2}$', p)                                          # x^{2.5}, 10^{n-1}
        p = re.sub(rf'(\d\s?|/)({UNIT})([234])\b', lambda m: m.group(1) + m.group(2) + m.group(3).translate(SUP), p)   # 9600 mm2, kg/m3
        p = re.sub(r'\b([kM]?N)\s?\.\s?(m)\b', r'\1·\2', p)                                                           # N.m, kN.m
        parts[k] = p.replace(' -> ', ' → ').replace(' <- ', ' ← ').replace(' => ', ' ⇒ ')                                # arrows typed as text
    return ''.join(parts)


def inline(tex):
    """Maths inside a sentence: sums and products with their limits beside the sign (as in running text), not stacked
    above and below it, so the line keeps its height."""
    t = normalize(tex)
    t = re.sub(r'\\sum(?=\s*[_^])', r'\\Sigma', t)
    t = re.sub(r'\\prod(?=\s*[_^])', r'\\Pi', t)
    return re.sub(r'\\(lim|max|min|sup|inf)(?=\s*_)', r'\\mathrm{\1}', t)


def lines(tex):
    """A display formula as the lines to draw: the rows of align/gather, or rows split by \\\\, each on its own line."""
    tex = re.sub(r'\\\\(?=[A-Za-z]{2})', r'\\', tex)            # \\frac over-escaped: a command, not a row break
    m = re.fullmatch(r'\s*\\begin\{(' + '|'.join(ROWS_ENVS) + r')\*?\}(?:\{[^{}]*\})?(.*)\\end\{\1\*?\}\s*', tex, re.S)
    body = m.group(2) if m else tex
    if '\\begin{' in body or '\\\\' not in body: return [display(tex if not m else body)]
    return [display(' '.join(r)) for r in _rows(body)]


BAD = re.compile(r'\\begin|\\end')          # what is left after normalize() that mathtext still cannot draw
