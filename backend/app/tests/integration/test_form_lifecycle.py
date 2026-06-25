"""Form lifecycle (review → approve → publish), sign-off, freeze, and QA report."""

from __future__ import annotations


def _assemble_form(client, *, pool_id: str = "small_2pl") -> tuple[str, str]:
    """Create a single-form minimax test, assemble it, return (test_id, form_id)."""
    tid = client.post("/api/v1/tests", json={"name": "gov", "pool_id": pool_id}).json()[
        "id"
    ]
    client.patch(
        f"/api/v1/tests/{tid}",
        json={
            "blueprint": {
                "name": "gov-bp",
                "length": 8,
                "statistical_target": {
                    "theta_points": [-1, 0, 1],
                    "target_info": [3, 4, 3],
                    "method": "minimax",
                },
                "content_constraints": [
                    {"tag_type": "KC", "tag_value": "algebra", "minimum": 2}
                ],
            }
        },
    )
    job = client.post(
        f"/api/v1/tests/{tid}/assemble", json={"strategy": "mip", "time_limit_s": 5}
    ).json()
    return tid, job["form_ids"][0]


def _transition(client, form_id, action, **kw):
    return client.post(
        f"/api/v1/forms/{form_id}/transition", json={"action": action, **kw}
    )


def test_full_happy_path_and_signoff_attribution(client) -> None:
    _, form_id = _assemble_form(client)
    assert client.get(f"/api/v1/forms/{form_id}").json()["lifecycle_state"] == "draft"

    steps = [
        ("submit_for_review", {"actor": "author@x"}, "content_review"),
        (
            "approve_content",
            {"actor": "sme@x", "actor_role": "content_reviewer"},
            "psychometric_review",
        ),
        (
            "approve_psychometric",
            {"actor": "psy@x", "actor_role": "psychometrician"},
            "approved",
        ),
        ("publish", {"actor": "admin@x", "actor_role": "publisher"}, "published"),
    ]
    for action, kw, expected in steps:
        body = _transition(client, form_id, action, **kw).json()
        assert body["state"] == expected

    lc = client.get(f"/api/v1/forms/{form_id}/lifecycle").json()
    assert lc["state"] == "published"
    # sign-off trail: 4 events, oldest first, with claimed actor/role recorded
    actions = [e["action"] for e in lc["events"]]
    assert actions == [s[0] for s in steps]
    assert lc["events"][1]["actor"] == "sme@x"
    assert lc["events"][1]["actor_role"] == "content_reviewer"
    # withdraw published -> draft
    assert (
        _transition(client, form_id, "withdraw", actor="admin@x").json()["state"]
        == "draft"
    )


def test_withdraw_returns_to_draft_and_requires_full_re_review(client) -> None:
    """Withdraw → draft; re-publishing must re-run BOTH gates (no stale-approval)."""
    _, form_id = _assemble_form(client)
    for action, kw in [
        ("submit_for_review", {}),
        ("approve_content", {"actor": "sme", "actor_role": "content_reviewer"}),
        ("approve_psychometric", {"actor": "psy", "actor_role": "psychometrician"}),
        ("publish", {"actor": "admin", "actor_role": "publisher"}),
    ]:
        _transition(client, form_id, action, **kw)
    # withdraw lands in draft (a non-released state), not approved
    assert _transition(client, form_id, "withdraw", actor="admin").json()["state"] == (
        "draft"
    )
    # no shortcut back to published — the gates must be re-run from scratch
    assert _transition(client, form_id, "publish").status_code == 409
    assert _transition(client, form_id, "approve_psychometric").status_code == 409
    _transition(client, form_id, "submit_for_review")
    body = _transition(client, form_id, "approve_content", actor="sme").json()
    assert body["state"] == "psychometric_review"


def test_invalid_transition_rejected(client) -> None:
    _, form_id = _assemble_form(client)
    # cannot publish straight from draft
    r = _transition(client, form_id, "publish")
    assert r.status_code == 409
    assert "cannot 'publish'" in r.json()["detail"]


def test_return_to_draft_requires_comment(client) -> None:
    _, form_id = _assemble_form(client)
    _transition(client, form_id, "submit_for_review")
    no_comment = _transition(client, form_id, "return_to_draft", actor="sme@x")
    assert no_comment.status_code == 409
    ok = _transition(
        client, form_id, "return_to_draft", actor="sme@x", comment="key imbalance"
    )
    assert ok.status_code == 200 and ok.json()["state"] == "draft"
    # the rejection comment is on the sign-off trail
    events = ok.json()["events"]
    assert events[-1]["comment"] == "key imbalance"


def test_role_hook_is_permissive(client) -> None:
    # any actor/role may perform a gated transition (enforcement is a stub)
    _, form_id = _assemble_form(client)
    _transition(client, form_id, "submit_for_review")
    # approve_content with NO role still succeeds (permissive)
    r = _transition(client, form_id, "approve_content", actor="whoever")
    assert r.status_code == 200 and r.json()["state"] == "psychometric_review"


def test_form_frozen_once_in_review(client) -> None:
    tid, form_id = _assemble_form(client)
    _transition(client, form_id, "submit_for_review")
    # blueprint edit blocked
    edit = client.patch(
        f"/api/v1/tests/{tid}",
        json={
            "blueprint": {
                "name": "x",
                "length": 8,
                "statistical_target": {"theta_points": [0], "target_info": [3]},
            }
        },
    )
    assert edit.status_code == 409
    # re-assembly blocked
    reassemble = client.post(
        f"/api/v1/tests/{tid}/assemble", json={"strategy": "mip", "time_limit_s": 5}
    )
    assert reassemble.status_code == 409
    # returning to draft unfreezes
    _transition(client, form_id, "return_to_draft", actor="sme", comment="rework")
    assert client.post(
        f"/api/v1/tests/{tid}/assemble", json={"strategy": "mip", "time_limit_s": 5}
    ).status_code in (200, 201)


def test_available_actions_track_state(client) -> None:
    _, form_id = _assemble_form(client)
    lc = client.get(f"/api/v1/forms/{form_id}/lifecycle").json()
    assert lc["available_actions"] == ["submit_for_review"]
    assert lc["frozen"] is False
    _transition(client, form_id, "submit_for_review")
    lc = client.get(f"/api/v1/forms/{form_id}/lifecycle").json()
    assert set(lc["available_actions"]) == {"approve_content", "return_to_draft"}
    assert lc["frozen"] is True


def test_qa_report_contents(client) -> None:
    _, form_id = _assemble_form(client)
    qa = client.get(f"/api/v1/forms/{form_id}/qa-report").json()
    assert qa["n_items"] == 8
    assert qa["metric"] == "logistic-D1-slope-intercept"
    assert len(qa["answer_key"]) == 8
    assert qa["answer_key"][0]["position"] == 1
    # key balance distribution
    assert qa["key_balance"]["n"] >= 0 and isinstance(qa["key_balance"]["counts"], dict)
    # coverage row for the algebra constraint
    labels = [c["label"] for c in qa["coverage"]]
    assert any("algebra" in lbl for lbl in labels)
    # psychometric curve: SE(θ)=1/√I and TCC(θ)=ΣP present across the grid
    assert len(qa["curve"]) == 13
    mid = next(p for p in qa["curve"] if p["theta"] == 0.0)
    assert mid["information"] > 0 and mid["se"] is not None
    assert 0.0 <= mid["tcc"] <= 8.0
    assert 0.0 <= qa["marginal_reliability"] <= 1.0
    assert len(qa["tif_actual_vs_target"]) == 3
