"""Cross-validation endpoint: OR-Tools form vs. the eatATA oracle (read-only).

The real eatATA correctness on the fixtures is covered by the CI oracle-parity gate
(``test_mip_matches_r_oracle``). Here we test the endpoint's comparison logic and
its graceful paths by stubbing the oracle-r HTTP call, so it runs without R.
"""

from __future__ import annotations

import urllib.error
from collections.abc import Callable

import pytest

from app.assembly.oracles import r_oracle
from app.assembly.oracles.r_oracle import ROracleResult


def _make_form(client, *, pool_id: str = "small_2pl") -> tuple[str, list[str]]:
    """Create a test, set a single-form minimax blueprint, assemble, return form."""
    resp = client.post("/api/v1/tests", json={"name": "xval", "pool_id": pool_id})
    tid = resp.json()["id"]
    blueprint = {
        "name": "xval-bp",
        "length": 8,
        "statistical_target": {
            "theta_points": [-1, 0, 1],
            "target_info": [3, 4, 3],
            "method": "minimax",
        },
    }
    client.patch(f"/api/v1/tests/{tid}", json={"blueprint": blueprint})
    job = client.post(
        f"/api/v1/tests/{tid}/assemble", json={"strategy": "mip", "time_limit_s": 5}
    ).json()
    form_id = job["form_ids"][0]
    items = client.get(f"/api/v1/forms/{form_id}").json()["item_ids"]
    return form_id, items


def _stub(monkeypatch: pytest.MonkeyPatch, fn: Callable[..., ROracleResult]) -> None:
    monkeypatch.setattr(r_oracle, "run_oracle_http", fn)


def test_cross_validate_reports_agreement(client, monkeypatch) -> None:
    form_id, items = _make_form(client)
    ot_obj = client.get(f"/api/v1/forms/{form_id}").json()
    # stub the oracle to return the SAME selection (agreement) + matching objective
    _stub(
        monkeypatch,
        lambda problem, **kw: ROracleResult(
            status="optimal",
            objective_value=0.123,
            item_ids=list(items),
            package="eatATA",
            solver="lpSolve",
            solve_time_s=0.05,
        ),
    )
    # make the stored OR-Tools objective match within tolerance
    r = client.post(f"/api/v1/forms/{form_id}/cross-validate")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["oracle"]["solver"] == "lpSolve"
    c = body["comparison"]
    assert c["selection_match"] is True
    assert c["only_in_ortools"] == [] and c["only_in_oracle"] == []
    assert c["jaccard"] == pytest.approx(1.0)
    assert c["constraints_satisfied"] is True
    assert ot_obj  # form readable


def test_cross_validate_reports_divergence(client, monkeypatch) -> None:
    form_id, items = _make_form(client)
    # oracle returns a different set (swap one item) -> divergence surfaced
    other = items[:-1] + ["__different__"]
    _stub(
        monkeypatch,
        lambda problem, **kw: ROracleResult(
            status="optimal",
            objective_value=99.0,  # far from OR-Tools -> outside tolerance
            item_ids=other,
            package="eatATA",
            solver="lpSolve",
        ),
    )
    body = client.post(f"/api/v1/forms/{form_id}/cross-validate").json()
    assert body["status"] == "ok"
    c = body["comparison"]
    assert c["selection_match"] is False
    assert "__different__" in c["only_in_oracle"]
    assert len(c["only_in_ortools"]) == 1
    assert c["jaccard"] < 1.0
    assert c["objective_within_tolerance"] is False


def test_cross_validate_oracle_unavailable(client, monkeypatch) -> None:
    form_id, _ = _make_form(client)

    def boom(problem, **kw):
        raise urllib.error.URLError("connection refused")

    _stub(monkeypatch, boom)
    body = client.post(f"/api/v1/forms/{form_id}/cross-validate").json()
    assert body["status"] == "oracle_unavailable"
    assert body["comparison"] is None


def test_cross_validate_unsupported_for_maximin(client, monkeypatch) -> None:
    tid = client.post(
        "/api/v1/tests", json={"name": "mm", "pool_id": "small_2pl"}
    ).json()["id"]
    client.patch(
        f"/api/v1/tests/{tid}",
        json={
            "blueprint": {
                "name": "mm",
                "length": 8,
                "statistical_target": {
                    "theta_points": [0],
                    "target_info": [3],
                    "method": "maximin",
                },
            }
        },
    )
    job = client.post(
        f"/api/v1/tests/{tid}/assemble", json={"strategy": "mip", "time_limit_s": 5}
    ).json()
    form_id = job["form_ids"][0]
    # should short-circuit before calling the oracle at all
    _stub(monkeypatch, lambda *a, **k: pytest.fail("oracle must not be called"))
    body = client.post(f"/api/v1/forms/{form_id}/cross-validate").json()
    assert body["status"] == "unsupported"
    assert "minimax" in body["detail"]


def test_cross_validate_missing_form(client) -> None:
    assert client.post("/api/v1/forms/does-not-exist/cross-validate").status_code == 404
