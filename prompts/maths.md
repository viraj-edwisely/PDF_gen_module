Maths is drawn by matplotlib's mathtext, which understands only part of LaTeX. Anything else is printed as raw text, so use only this:
- Inline maths between single dollars in any text field: `$t_k = k\Delta$`. Every `$` needs its closing `$` on the same line. A literal dollar sign is `\$`.
- Display maths in a "formula" block: {"type": "formula", "latex": "EA = PC + d"} (no dollars inside "latex"). One equation per block.
- Allowed: `^{...}` `_{...}` `\frac{a}{b}` `\sqrt{x}` `\sqrt[3]{x}` `\times` `\cdot` `\div` `\pm` `\leq` `\geq` `\neq` `\approx` `\equiv` `\infty` `\rightarrow` `\Rightarrow` `\leftrightarrow` `\in` `\subseteq` `\cup` `\cap` `\wedge` `\vee` `\neg` `\oplus` `\sum_{i=1}^{n}` `\prod` `\int_{a}^{b}` `\log` `\ln` `\sin` `\cos` `\lim` `\max` `\min` `\lceil x \rceil` `\lfloor x \rfloor` `\left( ... \right)` `\overline{x}` `\hat{x}` `\vec{x}` `\mathrm{text}` `\mathbf{x}` Greek letters (`\alpha` ... `\Omega`).
- Never use: `\begin{...}` / `\end{...}` (cases, matrix, align, array), `&`, `\\` (line breaks), `\text{}` (write `\mathrm{}`), `\operatorname`, `\dfrac`, `\boxed`, `\cancel`, `\underbrace`, `\xrightarrow`.
- A piecewise rule, a matrix, a truth table or several aligned lines is a "table" block or several "formula" blocks, never one LaTeX environment.
- Plain numbers, code, register names and hexadecimal values are plain text, not maths: write 2E0C (hex) or 2E0CH, not $2E0C_{H}$. Keep maths for real formulas.
- Fractions are \frac{numerator}{denominator}, never a/b with a slash, in formulas and in working (the app draws them full size).
- Powers and subscripts always in braces when longer than one character: 10^{-3}, e^{-j\omega t}, V_{max}.
- Units are plain text outside maths, written with their characters: 9600 mm², 20.48 × 10⁶ mm⁴, 1000 kg/m³, 9.81 m/s², 30 kN·m.
  Inside a formula they are \mathrm{...}: 2.000\ \mathrm{kJ}. Never m$^3$, m^3 or m3 in running text.
- A power of ten in running text is 20.48 × 10⁶ (characters), not 20.48 x 10^6.
