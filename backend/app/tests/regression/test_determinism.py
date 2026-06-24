"""Golden-fixture guards: pin the deterministic outputs so the metric layer,
compiler, and engine can't silently drift."""

from __future__ import annotations

import pytest

from app.assembly import assemble, compile_blueprint
from app.assembly.oracles.reference import exhaustive_assemble


def test_exhaustive_golden_form_and_objective(tiny_pool, tiny_blueprint) -> None:
    """The provably-optimal pick for the tiny fixture is fixed (no drift)."""
    problem = compile_blueprint(tiny_blueprint, tiny_pool)
    res = exhaustive_assemble(problem)
    assert res.status == "optimal"
    assert res.form_indices is not None and res.objective_value is not None
    form = sorted(problem.item_ids[i] for i in res.form_indices)
    # Canonical metric is logistic D=1 (matches mirt 1.46.1). Pinned for that metric.
    assert form == ["T0", "T4", "T6", "T7"]
    assert res.objective_value == pytest.approx(0.0496, abs=0.001)


def test_mip_objective_reproducible(tiny_pool, tiny_blueprint) -> None:
    """Same fixture + seed → same optimal objective across runs."""
    a = assemble(tiny_blueprint, tiny_pool, strategy="mip", time_limit_s=5, seed=0)
    b = assemble(tiny_blueprint, tiny_pool, strategy="mip", time_limit_s=5, seed=0)
    assert a.objective_value is not None
    assert a.objective_value == pytest.approx(b.objective_value, abs=0.001)


def test_random_constrained_deterministic_by_seed(
    default_pool, linear_blueprint
) -> None:
    """The low-rigor strategy is byte-for-byte reproducible by seed."""
    a = assemble(linear_blueprint, default_pool, strategy="random_constrained", seed=42)
    b = assemble(linear_blueprint, default_pool, strategy="random_constrained", seed=42)
    assert a.forms[0].item_ids == b.forms[0].item_ids
