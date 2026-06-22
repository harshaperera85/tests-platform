"""Regression: the owned OR-Tools engine matches independent oracles (plan §6).

Two oracle paths, both DEV/TEST ONLY (never in the runtime path):

* the pure-Python exhaustive reference — provably optimal on a tiny fixture, always
  available, so parity is enforced on every CI run;
* the R oracle (``eatATA`` / ``TestDesign``) — the canonical psychometric oracle,
  skipped when R / the packages are absent (e.g. on the host).
"""

from __future__ import annotations

import pytest

from app.assembly import assemble, compile_blueprint
from app.assembly.oracles import r_oracle
from app.assembly.oracles.reference import exhaustive_assemble


def test_mip_matches_exhaustive_optimum(tiny_pool, tiny_blueprint) -> None:
    problem = compile_blueprint(tiny_blueprint, tiny_pool)

    reference = exhaustive_assemble(problem)
    assert reference.status == "optimal"

    mip = assemble(tiny_blueprint, tiny_pool, strategy="mip", time_limit_s=5)
    assert mip.status == "optimal"

    # Objective parity within the integer-scaling resolution of the engine.
    assert mip.objective_value == pytest.approx(reference.objective_value, abs=0.01)


def test_mip_solution_satisfies_reference_feasibility(
    tiny_pool, tiny_blueprint
) -> None:
    problem = compile_blueprint(tiny_blueprint, tiny_pool)
    mip = assemble(tiny_blueprint, tiny_pool, strategy="mip", time_limit_s=5)
    chosen = tuple(sorted(problem.item_ids.index(i) for i in mip.forms[0].item_ids))
    # The engine's own pick must be feasible under the independent checker.
    from app.assembly.oracles.reference import _is_feasible

    assert _is_feasible(problem, chosen)


@pytest.mark.skipif(
    not r_oracle.is_available("eatATA"),
    reason="R / eatATA not installed (runs only in the scoring-r oracle image)",
)
def test_mip_matches_r_oracle(tiny_pool, tiny_blueprint) -> None:  # pragma: no cover
    problem = compile_blueprint(tiny_blueprint, tiny_pool)
    mip = assemble(tiny_blueprint, tiny_pool, strategy="mip", time_limit_s=5)
    r_result = r_oracle.run_oracle(problem, package="eatATA")
    assert r_result.status == "optimal"
    assert mip.objective_value == pytest.approx(r_result.objective_value, abs=0.05)
