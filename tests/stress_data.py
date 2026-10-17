"""Formulas and figure specs that once broke, or could break, a PDF. Used by test_drawing.py and stress_pdf.py."""

CORPUS = r"""
\frac{T}{J} = \frac{\tau}{R} = \frac{C\theta}{L}
\tau_{\max} = \frac{16T}{\pi D^3}
D = \sqrt[3]{\frac{16T}{\pi\tau}}
D = \left(\frac{32TL}{\pi C\theta(1-k^4)}\right)^{1/4}
\theta = \sum \frac{T_i l_i}{C_i I_{p_i}}
X(j\omega) = \int_{-\infty}^{\infty} x(t)e^{-j\omega t}\,dt
x(t) = \frac{1}{2\pi}\int_{-\infty}^{\infty} X(j\omega)e^{j\omega t}\,d\omega
X_p(j\omega) = 2\pi\sum_{k=-\infty}^{\infty} a_k\,\delta(\omega - k\omega_0)
\lim_{\omega \to 0} \frac{2\sin(\omega T_1)}{\omega} = 2T_1
u(t) \leftrightarrow \pi\delta(\omega) + \frac{1}{j\omega}
x(t) \leftrightarrow X(j\omega) \Rightarrow X(t) \leftrightarrow 2\pi x(-\omega)
\angle Y(j\omega) = -\omega
|X(j4)| = 1/\sqrt{3^2+4^2} = 0.20
\mathrm{EA} = 2E0C_H
\text{Effective address} = \text{base} + \text{offset}
\operatorname{sinc}(x) = \frac{\sin x}{x}
\dfrac{a}{b} + \tfrac{c}{d}
a \le b \ge c \ne d \approx e \equiv f
P(A \cap B) = P(A)P(B \mid A)
\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i,\quad \sigma^2 = E[(X-\mu)^2]
\binom{n}{k} p^k (1-p)^{n-k}
\vec{F} = m\vec{a},\ \hat{n},\ \overline{AB},\ \dot{x},\ \ddot{x}
\nabla \cdot \vec{E} = \frac{\rho}{\varepsilon_0}
\mathbf{A}\mathbf{x} = \mathbf{b},\ \det(A) = 0
\int_0^{\pi/2} \sin^2 x\, dx = \frac{\pi}{4}
\frac{\partial^2 u}{\partial x^2} + \frac{\partial^2 u}{\partial y^2} = 0
T = \frac{60 \times 1000 \times P}{2\pi N} = 2387.3\ \mathrm{N\cdot m}
\sigma = 42.46\ \mathrm{MPa},\ 25^\circ\mathrm{C},\ 50\%
\eta = 1 - \frac{T_L}{T_H} = 0.4
\Delta G^\circ = -RT\ln K
\log_2 1024 = 10,\quad \lceil \log_2 n \rceil,\ \lfloor n/2 \rfloor
O(n \log n),\ \Theta(n^2),\ \Omega(1)
A \land B \lor \lnot C \implies D \iff E
\forall x\, \exists y: x < y,\quad x \in \mathbb{R}
\{1, 2, 3\} \cup \{4\} = \{1,2,3,4\}
f(x) = \begin{cases} 1 & x > 0 \\ 0 & x \le 0 \end{cases}
\begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}
\boxed{x = 2}
x \xrightarrow{f} y
\underbrace{a+b}_{n}
G(s) = \frac{K}{s(s+2)(s+5)},\quad s = \sigma + j\omega
V_{out} = -\frac{R_f}{R_1}V_{in}
I = \frac{V}{R} = 2\,\mathrm{mA},\ 10\,\mu\mathrm{F},\ 5\,\Omega
\mathrm{RMS} = \frac{V_m}{\sqrt{2}}
y[n] = \sum_{k=0}^{N-1} h[k]\, x[n-k]
H(e^{j\omega}) = \frac{1}{1 - 0.5e^{-j\omega}}
\left| \frac{a}{b} \right|,\ \left[ x \right],\ \left\{ y \right\}
\mathcal{L}\{f(t)\} = F(s)
a \cdot b \times c \div d \pm e \mp f
x' = \frac{dx}{dt},\ f''(x)
10^{-3}\ \mathrm{m}^3,\ 2.356 \times 10^{-3}
1 + \frac{d^2}{D^2}
\frac{U_H}{U_S} = 0.8704
\text{rate} = 12\%\ \text{p.a.}
"""
FORMULAS = [t.strip() for t in CORPUS.strip().splitlines() if t.strip()]

AWKWARD = [
    ('plot: one labelled curve, axes at zero, negative values', 'plot', {'xlabel': r't (s)', 'ylabel': r'x(t)', 'axes_at_zero': True, 'grid': True,
        'curves': [{'x': [-2, -1, -1, 1, 1, 2], 'y': [0, 0, 1, 1, 0, 0], 'label': 'ideal pulse'},
                   {'expr': 'sin(3*x)/(3*x+1e-9)', 'range': [-2, 2], 'label': 'truncated inverse', 'style': '--'}]}),
    ('plot: spectrum with fill and annotations, labels in LaTeX', 'plot', {'xlabel': r'\omega (rad/s)', 'ylabel': r'X(j\omega)', 'axes_at_zero': True,
        'curves': [{'x': [-6, -5, -5, 5, 5, 6], 'y': [0, 0, 1, 1, 0, 0], 'fill': True, 'label': r'X(j\omega)'}],
        'annotations': [{'xy': [5, 1], 'text': 'cut-off W = 5', 'xytext': [5.5, 1.15]}]}),
    ('plot: impulse stems', 'plot', {'xlabel': 'ω (rad/s)', 'ylabel': 'weight', 'axes_at_zero': True,
        'curves': [{'x': [-4, 4], 'y': [3.14, 3.14], 'stem': True, 'label': 'π each'}]}),
    ('plot: large numbers and points', 'plot', {'xlabel': 'shaft rotation θ (rad)', 'ylabel': 'torque T (N·m)', 'grid': True,
        'curves': [{'expr': '4774.6 + 1432.4*sin(x)', 'range': [0, 6.283], 'label': 'torque cycle'}],
        'hlines': [{'y': 6207, 'label': 'maximum torque', 'style': '--'}, {'y': 4774.6, 'label': 'mean torque', 'style': '--'}],
        'points': [{'x': 1.571, 'y': 6207, 'label': 'Tmax'}, {'x': 4.712, 'y': 3342.2, 'label': 'Tmin'}]}),
    ('plot: equal axes circles (cross-sections)', 'plot', {'equal': True, 'grid': False,
        'curves': [{'param': ['-1.6 + cos(t)', 'sin(t)'], 'range': [0, 6.2832], 'fill': True, 'label': 'solid'},
                   {'param': ['1.6 + cos(t)', 'sin(t)'], 'range': [0, 6.2832], 'label': 'hollow outer'},
                   {'param': ['1.6 + 0.6*cos(t)', '0.6*sin(t)'], 'range': [0, 6.2832], 'label': 'hollow inner', 'style': '--'}]}),
    ('bars: negative values and long category names', 'bars', {'categories': ['Mechanical Engineering', 'Electrical', 'Civil and Structural', 'CSE', 'ECE'],
        'series': [{'name': '2023', 'values': [12, -4, 7.5, 30, 18]}, {'name': '2024', 'values': [15, 3, -2, 33, 21]}], 'ylabel': 'growth (%)'}),
    ('graph: two nodes, small', 'graph', {'nodes': [{'id': 'A', 'label': 'x(t)'}, {'id': 'B', 'label': 'H(jω)', 'shape': 'box'}], 'edges': [['A', 'B']]}),
    ('graph: wide block diagram, long labels', 'graph', {'rankdir': 'LR', 'nodes': [{'id': 'x', 'label': 'x(t)', 'shape': 'plaintext'},
        {'id': 'h1', 'label': 'H1(jω) = 1/(2 + jω)', 'shape': 'box'}, {'id': 'h2', 'label': 'H2(jω) = 1/(3 + jω)', 'shape': 'box'},
        {'id': 'y', 'label': 'Y(jω) = X(jω)H1(jω)H2(jω)', 'shape': 'box', 'fill': 'gold'}], 'edges': [['x', 'h1'], ['h1', 'h2'], ['h2', 'y']]}),
    ('graph: 14-node tree', 'graph', {'directed': False, 'nodes': [str(v) for v in [50, 30, 70, 20, 40, 60, 80, 10, 25, 35, 45, 55, 65, 75]],
        'edges': [['50', '30'], ['50', '70'], ['30', '20'], ['30', '40'], ['70', '60'], ['70', '80'], ['20', '10'], ['20', '25'], ['40', '35'], ['40', '45'], ['60', '55'], ['60', '65'], ['80', '75']]}),
    ('cells: 20 references, 3 frames', 'cells', {'index': [str(x) for x in [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]],
        'rows': [{'label': f'F{k}', 'cells': [str((k * 3 + j) % 8) for j in range(20)]} for k in range(3)] +
                [{'label': 'Fault', 'cells': [{'text': 'F', 'fill': 'accent'} if j % 3 else 'H' for j in range(20)]}]}),
    ('cells: instruction format with long fields', 'cells', {'rows': [{'label': 'Format', 'cells': ['Opcode (6 bits)', 'Mode (2)', 'Register (4)', 'Address / displacement (20 bits)']}]}),
    ('gantt: many short segments', 'gantt', {'segments': [[f'P{(i % 5) + 1}', i, i + 1] for i in range(24)]}),
    ('beam: stepped shaft as beam', 'beam', {'length': 1.5, 'supports': [{'x': 0, 'type': 'fixed'}],
        'loads': [{'type': 'moment', 'x': 1.5, 'label': '500 N·m', 'ccw': True}], 'sections': [[0, 1, 40, 'd = 40 mm'], [1, 1.5, 30, 'd = 30 mm']], 'dims': [[0, 1, '1 m'], [1, 1.5, '0.5 m']], 'points': {'A': 0, 'B': 1, 'C': 1.5}}),
]
B = chr(92) * 2      # a LaTeX row break
FORMULAS += [r'\begin{aligned} a &= b + c ' + B + r' &= d \end{aligned}', 'x = 1 ' + B + ' y = 2',
             r'\det\begin{vmatrix} a & b ' + B + r' c & d \end{vmatrix} = ad - bc', r'{n \choose k} \lVert x \rVert \lt 1 \tag{2}']
