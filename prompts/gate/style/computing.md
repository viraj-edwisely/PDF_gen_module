# Conventions for CS and DA

- State every assumption a question depends on: word size, byte addressing, signed or unsigned, little or big endian,
  0-based or 1-based indexing, time units (ms, ns), whether context-switch time is zero.
- Logarithms are base 2 unless stated; KB = 2¹⁰ bytes, MB = 2²⁰, GB = 2³⁰ for memory sizes; 10³ for data rates (kbps).
- Operating systems: arrival time AT, burst time BT, completion CT, turnaround TAT = CT − AT, waiting WT = TAT − BT,
  response RT = first run − AT; ties broken by arrival order, then by process number (say so).
- Algorithms: asymptotic notation O, Θ, Ω used precisely; recurrences solved by the master theorem only when it applies.
- Databases: relational algebra and SQL with the schema stated; functional dependencies X → Y.
- Theory of computation: DFA/NFA/PDA with start state and accepting states marked; Σ stated.
- Networks: bandwidth in bps (10³), propagation delay and transmission delay named separately; header sizes given.
- DA: probability notation P(A), E[X], Var(X); vectors bold or with arrows, stated once.
- Typical traps: off-by-one indexing, KB as 10³ vs 2¹⁰, idle time in schedules, tie-breaking, sign extension, counting the
  first dispatch as a context switch, bits vs bytes, the base of a logarithm.
