"""Assembly validation oracles — **DEV / TEST ONLY. NEVER in the runtime path.**

Per plan §6 and CLAUDE.md golden rule 2, the owned OR-Tools engine is validated
against independent oracles on known fixtures before it is trusted:

- :mod:`reference` — an independent, pure-Python *exhaustive* optimizer. On a small
  fixture it computes the provably optimal objective by enumeration, with no shared
  code path with the CP-SAT engine. This is the always-available parity oracle.
- :mod:`r_oracle` — a bridge to the R packages ``TestDesign::Static`` / ``eatATA``
  (the canonical psychometric oracles). Requires R + those packages; skips
  gracefully when unavailable. GPL — used only as a dev-time oracle, never shipped.

Nothing in this package is imported by the engine, the strategies, or the API.
"""
