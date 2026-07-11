"""LOFT engine (BP-MODES-1 §4): binding rules, band acceptance, exposure-rate
mask, conformance records, both engines, and the registered strategy."""

from __future__ import annotations

import pytest

from app.assembly.loft import (
    LoftAssemblyError,
    PoolFormRef,
    assemble_loft_session,
)
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


# -------------------------------------- §4.3(c) pre-generated form pool (G2)
def _make_form_pool(default_pool, bp: Blueprint, k: int) -> list[PoolFormRef]:
    """Conforming candidates via the real per-session engine (distinct seeds)."""
    refs, seen = [], set()
    seed = 0
    while len(refs) < k:
        ids = tuple(
            assemble_loft_session(bp, default_pool, seed=seed).item_ids
        )
        seed += 1
        if tuple(sorted(ids)) in seen:
            continue
        seen.add(tuple(sorted(ids)))
        refs.append(PoolFormRef(form_id=f"f-{len(refs)}", item_ids=ids))
    return refs


def test_pregenerated_requires_form_pool(default_pool) -> None:
    with pytest.raises(LoftAssemblyError, match="form_pool"):
        assemble_loft_session(
            _loft_blueprint(), default_pool, engine="pregenerated"
        )


def test_pregenerated_draw_rotates_and_records(default_pool) -> None:
    bp = _loft_blueprint()
    refs = _make_form_pool(default_pool, bp, 4)
    draws: dict[str, int] = {}
    for _ in range(8):  # 2 full rotations over K=4
        form = assemble_loft_session(
            bp,
            default_pool,
            engine="pregenerated",
            seed=9,
            form_pool=refs,
            draw_counts=dict(draws),
        )
        r = form.record
        assert r["blueprint_conformant"] is True
        assert r["engine"] == "pregenerated"
        assert r["form_id"] in {ref.form_id for ref in refs}
        assert r["n_pool_forms"] == 4 and r["n_conforming"] == 4
        draws[r["form_id"]] = draws.get(r["form_id"], 0) + 1
    # least-drawn rotation: perfectly balanced after 2 rotations
    assert sorted(draws.values()) == [2, 2, 2, 2]


def test_pregenerated_draw_is_deterministic_and_order_independent(
    default_pool,
) -> None:
    bp = _loft_blueprint()
    refs = _make_form_pool(default_pool, bp, 3)
    pick = lambda pool_order: assemble_loft_session(  # noqa: E731
        bp, default_pool, engine="pregenerated", seed=5, form_pool=pool_order
    ).record["form_id"]
    assert pick(refs) == pick(list(reversed(refs)))  # C5: seed+form_id only


def test_pregenerated_excludes_nonconforming_never_administers(
    default_pool,
) -> None:
    bp = _loft_blueprint()
    good = _make_form_pool(default_pool, bp, 1)[0]
    stale = PoolFormRef(form_id="stale", item_ids=good.item_ids[:10])  # short
    alien = PoolFormRef(form_id="alien", item_ids=("ghost-1",) * 20)
    form = assemble_loft_session(
        bp,
        default_pool,
        engine="pregenerated",
        seed=1,
        form_pool=[stale, alien, good],
    )
    assert form.record["form_id"] == good.form_id
    assert form.record["n_nonconforming"] == 2
    assert sum("non-conforming" in w for w in form.warnings) == 2
    with pytest.raises(LoftAssemblyError, match="no conforming form"):
        assemble_loft_session(
            bp, default_pool, engine="pregenerated", seed=1,
            form_pool=[stale, alien],
        )


def test_pregenerated_band_recheck_excludes_out_of_band_form(default_pool) -> None:
    bp = _loft_blueprint(tolerance=1.0)
    good = tuple(
        assemble_loft_session(bp, default_pool, engine="cp_sat", seed=2).item_ids
    )
    # a content-feasible but band-agnostic form: assembled content-only, so its
    # TIF is very unlikely to sit inside the 1.0 band around the target
    loose = tuple(
        assemble_loft_session(
            _loft_blueprint(tolerance=None), default_pool, seed=99
        ).item_ids
    )
    form = assemble_loft_session(
        bp,
        default_pool,
        engine="pregenerated",
        seed=3,
        form_pool=[
            PoolFormRef(form_id="loose", item_ids=loose),
            PoolFormRef(form_id="good", item_ids=good),
        ],
    )
    assert form.record["form_id"] == "good"


def test_pregenerated_rate_cap_masks_forms(default_pool) -> None:
    bp = _loft_blueprint(exposure_target=ExposureTarget(max_exposure_rate=0.5))
    refs = _make_form_pool(default_pool, bp, 3)
    only_in_first = next(
        (i for i in refs[0].item_ids if all(i not in r.item_ids for r in refs[1:])),
        None,
    )
    if only_in_first is None:
        pytest.skip("no form-unique item in this draw — pool too overlapping")
    form = assemble_loft_session(
        bp,
        default_pool,
        engine="pregenerated",
        seed=4,
        form_pool=refs,
        usage_counts={only_in_first: 6},
        n_prior_sessions=10,  # 0.6 >= 0.5 -> refs[0] masked
    )
    assert form.record["form_id"] != refs[0].form_id
    assert form.record["n_rate_masked"] == 1
    # cap below the structural floor of a finite pool -> loud failure
    over_all = {i: 6 for r in refs for i in r.item_ids}
    with pytest.raises(LoftAssemblyError, match="structural floor"):
        assemble_loft_session(
            bp, default_pool, engine="pregenerated", seed=4, form_pool=refs,
            usage_counts=over_all, n_prior_sessions=10,
        )


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
