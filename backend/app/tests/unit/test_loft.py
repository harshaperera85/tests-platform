"""LOFT engine (BP-MODES-1 §4): binding rules, band acceptance, exposure-rate
mask, conformance records, both engines, and the registered strategy."""

from __future__ import annotations

import pytest

from app.assembly.loft import LoftAssemblyError, assemble_loft_session
from app.engine import registry
from app.engine.strategies import loft as loft_module  # noqa: F401 (registers)
from app.schemas.blueprint import (
    Blueprint,
    ContentConstraint,
    ExposureTarget,
    TIFTarget,
)
from app.schemas.test_config import LoftConfig


def _loft_blueprint(tolerance: float | None = 3.0, **kw) -> Blueprint:
    # mid-range target with a generous default band: engine (a) is a random
    # search, so acceptance-by-retry needs headroom; cp_sat holds tight bands
    # by construction (tested separately below).
    target = (
        TIFTarget(
            theta_points=[-1.0, 0.0, 1.0],
            target_info=[5.0, 6.5, 5.0],
            tolerance=tolerance,
        )
        if tolerance is not None
        else None
    )
    return Blueprint(
        name="loft-demo",
        length=20,
        statistical_target=target,
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="algebra", minimum=4, maximum=8),
            ContentConstraint(tag_type="KC", tag_value="geometry", minimum=4),
        ],
        **kw,
    )


# ------------------------------------------------------------- binding rules
def test_target_without_tolerance_rejected(default_pool) -> None:
    bp = Blueprint(
        length=10,
        statistical_target=TIFTarget(theta_points=[0.0], target_info=[5.0]),
    )
    with pytest.raises(LoftAssemblyError, match="tolerance"):
        assemble_loft_session(bp, default_pool)


def test_content_only_loft_legal_with_notice(default_pool) -> None:
    bp = _loft_blueprint(tolerance=None)
    form = assemble_loft_session(bp, default_pool, seed=3)
    assert len(form.item_ids) == 20
    assert any("content only" in w for w in form.warnings)
    assert form.record["blueprint_conformant"] is True
    assert form.record["tif_target"] == []  # nothing statistical claimed


def test_batch_exposure_fields_ignored_with_warning(default_pool) -> None:
    bp = _loft_blueprint(
        exposure_target=ExposureTarget(max_use_per_item=1, max_pairwise_overlap=5)
    )
    form = assemble_loft_session(bp, default_pool, seed=1)
    assert any("ignored under LOFT" in w for w in form.warnings)
    assert len(form.item_ids) == 20  # assembly unaffected by the batch fields


# ------------------------------------------------------- §4.1 band acceptance
@pytest.mark.parametrize(
    ("engine", "tolerance"),
    [("random_constrained", 3.0), ("cp_sat", 1.0)],  # (a) needs headroom; (b) tight
)
def test_band_is_hard_acceptance(default_pool, engine: str, tolerance: float) -> None:
    bp = _loft_blueprint(tolerance=tolerance)
    tgt = bp.statistical_target
    assert tgt is not None
    for seed in range(6):
        form = assemble_loft_session(bp, default_pool, engine=engine, seed=seed)
        for actual, target in zip(form.tif_actual, tgt.target_info, strict=True):
            assert abs(actual - target) <= tolerance + 1e-9, (engine, seed)
        assert form.record["blueprint_conformant"] is True
        assert form.record["engine"] == engine


@pytest.mark.parametrize("engine", ["random_constrained", "cp_sat"])
def test_impossible_band_fails_loudly(default_pool, engine: str) -> None:
    bp = Blueprint(
        length=5,  # 5 items cannot reach info 30
        statistical_target=TIFTarget(
            theta_points=[0.0], target_info=[30.0], tolerance=0.1
        ),
    )
    with pytest.raises(LoftAssemblyError):
        assemble_loft_session(bp, default_pool, engine=engine, seed=0)


def test_forms_are_diverse_across_seeds(default_pool) -> None:
    bp = _loft_blueprint(tolerance=1.5)
    forms = {
        tuple(
            sorted(
                assemble_loft_session(
                    bp, default_pool, engine="cp_sat", seed=s
                ).item_ids
            )
        )
        for s in range(8)
    }
    assert len(forms) >= 3  # randomized objective draws different conforming forms


def test_deterministic_given_seed(default_pool) -> None:
    bp = _loft_blueprint()
    a = assemble_loft_session(bp, default_pool, seed=42).item_ids
    b = assemble_loft_session(bp, default_pool, seed=42).item_ids
    assert a == b


# ------------------------------------------------------ §4.2 running rate cap
def test_exposure_rate_masks_overexposed_items(default_pool) -> None:
    bp = _loft_blueprint(
        tolerance=2.0,
        exposure_target=ExposureTarget(max_exposure_rate=0.5),
    )
    hot = default_pool.items[0].item_id
    form = assemble_loft_session(
        bp,
        default_pool,
        seed=1,
        usage_counts={hot: 6},
        n_prior_sessions=10,  # 0.6 >= 0.5 -> masked
    )
    assert hot not in form.item_ids
    assert any("masked 1 item" in w for w in form.warnings)


# --------------------------------------------------------- §4.4 record shape
def test_conformance_record_contents(default_pool) -> None:
    bp = _loft_blueprint()
    form = assemble_loft_session(bp, default_pool, seed=7)
    r = form.record
    assert r["blueprint_conformant"] is True
    assert r["realized_length"] == 20
    assert r["tolerance"] == 3.0 and r["seed"] == 7
    keys = {c["key"] for c in r["constraints"]}
    assert keys == {"KC=algebra", "KC=geometry"}
    assert all(c["satisfied"] for c in r["constraints"])
    alg = next(c for c in r["constraints"] if c["key"] == "KC=algebra")
    assert alg["required_min"] == 4 and alg["required_max"] == 8
    assert 4 <= alg["realized"] <= 8


# -------------------------------------------------------------- the strategy
def test_loft_strategy_registered_and_walks(default_pool) -> None:
    strategy = registry.get_strategy("loft")
    assert strategy.config_schema is LoftConfig

    bp = _loft_blueprint()
    state = strategy.initialize(
        LoftConfig(), default_pool, {"blueprint": bp, "session_id": "s-1", "seed": 5}
    )
    assert state.model_type == "loft"
    assert state.data["conformance_record"]["blueprint_conformant"] is True
    n = len(state.data["item_ids"])
    assert n == 20

    for i in range(n):
        action = strategy.next_action(state)
        assert action.kind == "present"
        state = strategy.record_response(state, {"correct": i % 2})
    assert strategy.is_complete(state).complete
    score = strategy.score(state)
    assert score.scale == "canonical"
    assert score.detail["blueprint_conformant"] is True


def test_loft_strategy_requires_blueprint(default_pool) -> None:
    strategy = registry.get_strategy("loft")
    with pytest.raises(ValueError, match="blueprint"):
        strategy.initialize(LoftConfig(), default_pool, {"session_id": "s"})


def test_loft_strategy_per_session_forms_differ(default_pool) -> None:
    strategy = registry.get_strategy("loft")
    bp = _loft_blueprint(tolerance=1.5)
    cfg = LoftConfig(engine="cp_sat")
    forms = {
        tuple(
            sorted(
                strategy.initialize(
                    cfg, default_pool, {"blueprint": bp, "session_id": f"s-{k}"}
                ).data["item_ids"]
            )
        )
        for k in range(6)
    }
    assert len(forms) >= 2  # different sessions, different conforming forms
