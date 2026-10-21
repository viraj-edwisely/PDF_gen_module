# Conventions for EC, EE and IN

- Units: SI; frequencies in Hz/kHz/MHz with f, angular frequency ω = 2πf in rad/s; say which one a question uses.
  Decibels: 10 log₁₀ for power ratios, 20 log₁₀ for voltage/current ratios; convert dB to linear before any formula.
- Communications: message m(t), carrier c(t) = A_c cos 2πf_c t, modulation index μ (AM) and β (FM/PM), A_m, f_m, f_c;
  AM s(t) = A_c[1 + μ cos 2πf_m t] cos 2πf_c t; power in normalised form (R = 1 Ω) unless R is given; bandwidth of AM
  and DSB-SC 2f_m, SSB f_m, FM by Carson's rule 2(Δf + f_m). Spectra are one-sided amplitude spectra unless stated.
  Digital: E_b/N_0 in linear units inside Q(·); R_b = R_s log₂ M; raised-cosine bandwidth (1 + α)R_s (passband, state it).
- Signals and systems: x(t), h(t), X(jω) or X(f) (state which); unit step u(t), impulse δ(t); causal means h(t) = 0 for t < 0.
- Control: G(s), H(s), unity negative feedback unless stated; 2 % settling time 4/(ζω_n); peak overshoot e^{-ζπ/√(1-ζ²)}.
- Circuits: passive sign convention (current into the + terminal); phasors in RMS unless stated; j for √−1.
- Electronics: n-channel and npn by default; small-signal parameters g_m, r_π, r_o; thermal voltage V_T ≈ 25.9 mV at 300 K.
- Machines and power: per-unit values on the stated base; three-phase line and phase quantities named explicitly.
- GATE gives: component values, frequencies, and constants (Boltzmann, electron charge) when needed; it expects Q(·) or
  erfc values to be given or read from a table in the question.
- Typical traps: dB vs linear, ω vs f (a factor 2π), peak vs RMS, one-sided vs two-sided spectra and PSD, E_b vs E_s,
  bit rate vs symbol rate, over-modulation (μ > 1) breaking the envelope detector, sign of feedback.
