"""Cross-form comparability report: parallel forms pass; mismatched forms flag."""

from __future__ import annotations


def _assemble(client, target, *, num_forms=1, length=20, pool="small_2pl") -> list[str]:
    tid = client.post("/api/v1/tests", json={"name": "cmp", "pool_id": pool}).json()[
        "id"
    ]
    client.patch(
        f"/api/v1/tests/{tid}",
        json={
            "blueprint": {
                "name": "cmp-bp",
                "length": length,
                "num_forms": num_forms,
                "statistical_target": {
                    "theta_points": [-1, 0, 1],
                    "target_info": target,
                    "method": "minimax",
                },
                **(
                    {"exposure_target": {"max_pairwise_overlap": length // 2}}
                    if num_forms > 1
                    else {}
                ),
            }
        },
    )
    job = client.post(
        f"/api/v1/tests/{tid}/assemble", json={"strategy": "mip", "time_limit_s": 8}
    ).json()
    return job["form_ids"]


def test_parallel_forms_are_comparable(client) -> None:
    # two parallel forms assembled to the same target -> low divergence, pass
    form_ids = _assemble(client, [7, 9, 7], num_forms=2)
    assert len(form_ids) == 2
    r = client.post(
        "/api/v1/forms/compare",
        json={"form_ids": form_ids, "tolerance": 2.0, "score_tolerance": 2.0},
    ).json()
    assert r["n_forms"] == 2
    assert r["metric"] == "logistic-D1-slope-intercept"
    assert len(r["forms"]) == 2
    assert len(r["forms"][0]["curve"]) == 13
    assert "equating" in r["scope_note"].lower()
    assert r["passed"] is True
    assert r["max_tif_deviation"] <= 2.0
    assert not any(d["diverged"] for d in r["dispersion"])


def test_mismatched_forms_are_flagged(client) -> None:
    # one low-information form vs one high-information form -> divergence flagged
    low = _assemble(client, [2, 2, 2], length=20, pool="demo_mixed")[0]
    high = _assemble(client, [10, 12, 10], length=30, pool="demo_mixed")[0]
    r = client.post(
        "/api/v1/forms/compare",
        json={"form_ids": [low, high], "tolerance": 1.0, "score_tolerance": 1.0},
    ).json()
    assert r["passed"] is False
    assert r["flags"]  # non-empty
    assert r["max_tif_deviation"] > 1.0
    assert any(d["diverged"] for d in r["dispersion"])
    # per-form summary metrics present
    assert all("marginal_reliability" in f for f in r["forms"])


def test_compare_requires_two_forms(client) -> None:
    one = _assemble(client, [7, 9, 7])
    assert (
        client.post("/api/v1/forms/compare", json={"form_ids": one}).status_code == 422
    )


def test_compare_missing_form_404(client) -> None:
    one = _assemble(client, [7, 9, 7])
    r = client.post(
        "/api/v1/forms/compare", json={"form_ids": [one[0], "nope"]}
    )
    assert r.status_code == 404
