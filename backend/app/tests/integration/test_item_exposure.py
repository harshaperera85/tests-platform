"""Longitudinal item exposure: recording, query, and opt-in eligibility feedback."""

from __future__ import annotations

from app.assembly import assemble, compile_blueprint
from app.psychometrics.bank import load_pool
from app.schemas.blueprint import Blueprint, ExposureFeedback, TIFTarget


def _bp(**kw) -> Blueprint:
    return Blueprint(
        name="exp",
        length=20,
        statistical_target=TIFTarget(
            theta_points=[-1, 0, 1], target_info=[5, 5, 5], method="minimax"
        ),
        **kw,
    )


_POOL = "app/psychometrics/fixtures/small_2pl_bank.json"


# --- recording + query (API) -------------------------------------------------
def _assemble_form(client) -> tuple[str, str, list[str]]:
    tid = client.post(
        "/api/v1/tests", json={"name": "e", "pool_id": "small_2pl"}
    ).json()["id"]
    client.patch(
        f"/api/v1/tests/{tid}",
        json={
            "blueprint": {
                "name": "e",
                "length": 10,
                "statistical_target": {
                    "theta_points": [0],
                    "target_info": [4],
                    "method": "minimax",
                },
            }
        },
    )
    job = client.post(f"/api/v1/tests/{tid}/assemble", json={"time_limit_s": 6}).json()
    fid = job["form_ids"][0]
    items = client.get(f"/api/v1/forms/{fid}").json()["item_ids"]
    return tid, fid, items


def test_assembly_records_draft_and_publish_records_real_exposure(client) -> None:
    _, fid, items = _assemble_form(client)
    # assembly recorded 'assembled' (draft) usage by default
    exp = client.get("/api/v1/pool/exposure?pool_id=small_2pl").json()
    by_id = {e["item_id"]: e for e in exp["items"]}
    assert all(by_id[i]["assembled"] >= 1 for i in items)
    assert all(by_id[i]["published"] == 0 for i in items)  # not published yet

    # walk to published -> records 'published' (real) exposure
    for action, kw in [
        ("submit_for_review", {}),
        ("approve_content", {"actor": "sme", "actor_role": "content_reviewer"}),
        ("approve_psychometric", {"actor": "p", "actor_role": "psychometrician"}),
        ("publish", {"actor": "a", "actor_role": "publisher"}),
    ]:
        client.post(f"/api/v1/forms/{fid}/transition", json={"action": action, **kw})
    exp2 = client.get("/api/v1/pool/exposure?pool_id=small_2pl").json()
    by_id2 = {e["item_id"]: e for e in exp2["items"]}
    assert exp2["exposure_contexts"] == ["published"]
    assert all(by_id2[i]["published"] >= 1 for i in items)
    assert all(by_id2[i]["last_used"] for i in items)


# --- feedback OFF: byte-for-byte unchanged -----------------------------------
def test_feedback_off_is_identical_even_with_counts() -> None:
    pool = load_pool(_POOL)
    bp = _bp()  # no exposure_feedback
    counts = {it.item_id: 99 for it in list(pool.items)[:10]}
    p_no = compile_blueprint(bp, pool)
    p_counts = compile_blueprint(bp, pool, exposure_counts=counts)
    # exposure inputs are ignored without exposure_feedback → the compiled problem is
    # byte-for-byte identical. This model-identity is the deterministic guarantee that
    # default assembly is unchanged. (The *solve* result is not compared across two
    # runs: parallel CP-SAT can return different optima/objectives among ties — the
    # determinism golden covers solver reproducibility on a tiny proven-optimal pool.)
    assert p_no == p_counts
    assert p_no.excluded_indices == () and p_no.exposure == ()
    assert p_no.underuse_weight == 0.0
    # and it still assembles a valid form when counts are passed but feedback is off
    res = assemble(bp, pool, strategy="mip", time_limit_s=5, exposure_counts=counts)
    assert res.feasible and len(res.forms[0].item_ids) == 20


# --- feedback ON: hard-exclude over-exposed ----------------------------------
def test_eligibility_excludes_over_exposed_items() -> None:
    pool = load_pool(_POOL)
    off = assemble(_bp(), pool, strategy="mip", time_limit_s=5).forms[0].item_ids
    over = {iid: 5 for iid in off[:5]}  # 5 selected items are over-exposed
    bp = _bp(
        exposure_feedback=ExposureFeedback(
            count_contexts=["assembled"], max_cumulative=5
        )
    )
    on = (
        assemble(bp, pool, strategy="mip", time_limit_s=5, exposure_counts=over)
        .forms[0]
        .item_ids
    )
    assert len(on) == 20
    assert not any(iid in over for iid in on)  # over-exposed items excluded


# --- feedback ON: bidirectional under-use preference -------------------------
def test_underuse_preference_avoids_exposed_items() -> None:
    pool = load_pool(_POOL)
    off = assemble(_bp(), pool, strategy="mip", time_limit_s=5).forms[0].item_ids
    exposure = {iid: 10 for iid in off}  # the off-form's items are heavily used
    bp = _bp(
        exposure_feedback=ExposureFeedback(
            count_contexts=["assembled"], prefer_underused=True, underuse_weight=1.0
        )
    )
    on = (
        assemble(bp, pool, strategy="mip", time_limit_s=8, exposure_counts=exposure)
        .forms[0]
        .item_ids
    )
    on_exposure = sum(exposure.get(i, 0) for i in on)
    off_exposure = sum(exposure.get(i, 0) for i in off)
    # the under-use bias steers selection away from the heavily-used items
    assert on_exposure < off_exposure


def test_exposure_feedback_validation() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExposureFeedback()  # needs max_cumulative and/or prefer_underused+weight
