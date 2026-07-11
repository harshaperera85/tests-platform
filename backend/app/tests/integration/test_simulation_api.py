"""G1 measurement-simulation harness: recovery sanity, C5 pairing/determinism,
conditional bins, LOFT exposure/diversity, infeasibility accounting, §4 report."""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.psychometrics.bank import load_default_pool
from app.schemas.blueprint import Blueprint
from app.schemas.simulation import (
    Condition,
    LinearDesign,
    Population,
    SimulationRequest,
)
from app.simulation.harness import (
    _true_theta,
    compare_paired,
    run_condition,
    summarize,
)


def _bp_payload(tolerance: float | None = 2.5) -> dict:
    p: dict = {
        "name": "sim-study",
        "length": 20,
        "content_constraints": [
            {"tag_type": "KC", "tag_value": "algebra", "minimum": 4, "maximum": 8},
            {"tag_type": "KC", "tag_value": "geometry", "minimum": 4},
        ],
    }
    if tolerance is not None:
        p["statistical_target"] = {
            "theta_points": [-1.0, 0.0, 1.0],
            "target_info": [5.0, 6.5, 5.0],
            "tolerance": tolerance,
        }
    return p


# ---------------------------------------------------------------- population
def test_population_seeding_is_deterministic_and_plausible() -> None:
    pop = Population()
    thetas = [_true_theta(pop, seed=3, idx=i) for i in range(2000)]
    again = [_true_theta(pop, seed=3, idx=i) for i in range(2000)]
    assert thetas == again  # C5: derivation, not sequence
    m = sum(thetas) / len(thetas)
    sd = math.sqrt(sum((t - m) ** 2 for t in thetas) / (len(thetas) - 1))
    assert abs(m) < 0.1 and 0.9 < sd < 1.1  # N(0,1) recovered


# --------------------------------------------------------- service-level run
def _linear_condition(bp: Blueprint, pool) -> tuple:
    cond = Condition(name="lin", design=LinearDesign(blueprint_id="inline"))
    run = run_condition(
        cond,
        pool,
        blueprint=bp,
        form_item_ids=None,
        population=Population(),
        n_simulees=400,
        replications=1,
        seed=11,
    )
    return cond, run


def test_linear_recovery_sanity() -> None:
    pool = load_default_pool()
    bp = Blueprint.model_validate(_bp_payload())
    cond, run = _linear_condition(bp, pool)
    res = summarize(run, cond)
    o = res.overall
    assert o.n == 400
    assert abs(o.mean_bias) < 0.12  # EAP shrinkage keeps this small but nonzero
    assert 0.25 < o.rmse < 0.6  # plausible for a 20-item 2PL form
    assert o.correlation > 0.85 and o.reliability > 0.7
    assert 0.6 < o.shrinkage_ratio < 1.0  # EAP shrinks — the Embretson caution
    assert o.mean_length == 20
    # conditional bins populated and SE grows toward the tails vs center
    center = next(b for b in res.conditional if b.bin_center == 0.25)
    tail = next(b for b in res.conditional if b.bin_center == -2.75)
    assert center.n > 20
    if tail.n >= 5 and tail.csee and center.csee:
        assert tail.csee > center.csee


def test_same_condition_twice_pairs_exactly() -> None:
    """C5 item-level pairing: identical design ⇒ identical outcomes ⇒ Δ = 0."""
    pool = load_default_pool()
    bp = Blueprint.model_validate(_bp_payload())
    cond, run_a = _linear_condition(bp, pool)
    _, run_b = _linear_condition(bp, pool)
    cmp = compare_paired("a", run_a, "b", run_b)
    assert cmp.n_pairs == 400
    assert cmp.mean_abs_error_delta == 0.0
    assert cmp.rmse_a == cmp.rmse_b


# --------------------------------------------------------------- API studies
def test_linear_vs_loft_study(client: TestClient) -> None:
    bid = client.post("/api/v1/blueprints", json=_bp_payload()).json()["id"]
    resp = client.post(
        "/api/v1/simulations",
        json={
            "pool_id": "small_2pl",
            "n_simulees": 150,
            "seed": 5,
            "conditions": [
                {
                    "name": "linear baseline",
                    "design": {"kind": "linear", "blueprint_id": bid},
                },
                {"name": "loft", "design": {"kind": "loft", "blueprint_id": bid}},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # §4 report block
    r = body["report"]
    assert r["protocol"].startswith("G1 measurement simulation")
    assert r["lanes"][0]["lane"] == "in_process_same_engine"
    assert "ONLY the examinee is simulated" in r["lanes"][0]["coverage"]
    assert r["seeds"] == {"global": 5} and r["n_per_condition"] == 150

    lin, loft = body["conditions"]
    assert lin["kind"] == "linear" and loft["kind"] == "loft"
    # recovery in the same ballpark for both (Embretson parity expectation)
    for c in (lin, loft):
        assert c["overall"]["correlation"] > 0.8
        assert c["n_infeasible_sessions"] == 0
    # LOFT-only surfaces: diversity + overlap + solve times
    assert loft["exposure"]["n_distinct_forms"] > 10
    assert loft["exposure"]["mean_pairwise_overlap"] is not None
    assert loft["assembly_seconds_mean"] is not None
    assert lin["exposure"]["n_distinct_forms"] is None
    # linear exposure: every form item at rate 1.0
    assert lin["exposure"]["max_rate"] == 1.0 and lin["exposure"]["n_items_used"] == 20

    # paired comparison present with a defensible delta
    cmp = body["comparisons"][0]
    assert cmp["n_pairs"] == 150
    assert abs(cmp["mean_abs_error_delta"]) < 0.15
    assert cmp["p_value"] is None or 0.0 <= cmp["p_value"] <= 1.0

    assert len(body["scatter"]) > 100


def test_study_is_reproducible(client: TestClient) -> None:
    bid = client.post("/api/v1/blueprints", json=_bp_payload()).json()["id"]
    req = {
        "pool_id": "small_2pl",
        "n_simulees": 60,
        "seed": 9,
        "conditions": [
            {"name": "lin", "design": {"kind": "linear", "blueprint_id": bid}}
        ],
    }
    a = client.post("/api/v1/simulations", json=req).json()
    b = client.post("/api/v1/simulations", json=req).json()
    assert a["conditions"][0]["overall"] == b["conditions"][0]["overall"]
    assert a["scatter"] == b["scatter"]


def test_loft_infeasibility_is_counted_not_fatal(client: TestClient) -> None:
    payload = _bp_payload(tolerance=0.05)
    payload["statistical_target"]["target_info"] = [40.0, 40.0, 40.0]
    bid = client.post("/api/v1/blueprints", json=payload).json()["id"]
    resp = client.post(
        "/api/v1/simulations",
        json={
            "pool_id": "small_2pl",
            "n_simulees": 10,
            "conditions": [
                {
                    "name": "impossible loft",
                    "design": {
                        "kind": "loft",
                        "blueprint_id": bid,
                        "engine": "cp_sat",
                    },
                }
            ],
        },
    )
    assert resp.status_code == 200  # a study OBSERVES failure; it doesn't crash
    c = resp.json()["conditions"][0]
    assert c["n_infeasible_sessions"] == 10
    assert c["overall"]["n"] == 0


def test_validation_errors(client: TestClient) -> None:
    bid = client.post("/api/v1/blueprints", json=_bp_payload()).json()["id"]
    lin = {"name": "l", "design": {"kind": "linear", "blueprint_id": bid}}
    # unknown pool / blueprint
    assert (
        client.post(
            "/api/v1/simulations", json={"pool_id": "nope", "conditions": [lin]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/simulations",
            json={
                "pool_id": "small_2pl",
                "conditions": [
                    {"name": "x", "design": {"kind": "linear", "blueprint_id": "ghost"}}
                ],
            },
        ).status_code
        == 404
    )
    # study-size cap
    resp = client.post(
        "/api/v1/simulations",
        json={
            "pool_id": "small_2pl",
            "n_simulees": 2000,
            "replications": 20,
            "conditions": [lin],
        },
    )
    assert resp.status_code == 422
    # duplicate condition names
    resp = client.post(
        "/api/v1/simulations",
        json={"pool_id": "small_2pl", "conditions": [lin, lin]},
    )
    assert resp.status_code == 422


def test_request_schema_rejects_ambiguous_linear() -> None:
    with pytest.raises(ValueError):
        SimulationRequest.model_validate(
            {
                "pool_id": "small_2pl",
                "conditions": [
                    {"name": "x", "design": {"kind": "linear"}}  # neither source
                ],
            }
        )


def test_pregenerated_loft_condition(client: TestClient) -> None:
    """G2 in the G1 harness: the pool is batch-assembled ONCE by the real
    assemble(), then simulees draw with rotation — distinct forms ≤ K and
    recovery stays in the linear ballpark."""
    payload = _bp_payload()
    payload["exposure_target"] = {"max_use_per_item": 3}  # batch diversity
    bid = client.post("/api/v1/blueprints", json=payload).json()["id"]
    resp = client.post(
        "/api/v1/simulations",
        json={
            "pool_id": "small_2pl",
            "n_simulees": 90,
            "seed": 13,
            "conditions": [
                {
                    "name": "loft pregen",
                    "design": {
                        "kind": "loft",
                        "blueprint_id": bid,
                        "engine": "pregenerated",
                        "n_pool_forms": 6,
                    },
                },
                {"name": "loft live", "design": {"kind": "loft", "blueprint_id": bid}},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    pre, live = resp.json()["conditions"]
    assert pre["n_infeasible_sessions"] == 0
    assert pre["overall"]["n"] == 90 and pre["overall"]["correlation"] > 0.8
    # a finite pool: at most K distinct forms, rotation -> form rate ≈ 1/K
    assert 2 <= pre["exposure"]["n_distinct_forms"] <= 6
    assert live["exposure"]["n_distinct_forms"] > pre["exposure"]["n_distinct_forms"]
    # the batch-assembly provenance is surfaced, and draws are not solves
    assert any("batch-assembled" in w for w in pre["warnings"])
    assert pre["assembly_seconds_mean"] < 0.05  # draw, not solve
