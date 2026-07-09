"""Analysis client (scoring-r wrappers): payload discipline, honest surfacing,
prior requirement, PoolKind round-trip. HTTP is faked; live behavior is held by
the scoring-r build-time selftests + the stack smoke."""

from __future__ import annotations

import io
import json
import urllib.request
from typing import Any

import pytest
from pydantic import ValidationError

from app.psychometrics.analysis import (
    AnalysisServiceError,
    ItemParamsIn,
    ItemPrior,
    ResponseRecord,
    ScoredResponse,
    calibrate,
    link,
    score_person,
    update_item,
)
from app.psychometrics.params import require_metric


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_service(monkeypatch):
    """Capture the outgoing request; serve a canned JSON body."""
    calls: dict[str, Any] = {}

    def install(body: dict) -> dict[str, Any]:
        def fake_urlopen(req, timeout=None):
            calls["url"] = req.full_url
            calls["payload"] = json.loads(req.data)
            calls["timeout"] = timeout
            return _FakeResponse(json.dumps(body).encode())

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        return calls

    return install


METRIC = {"scaling_d": 1, "form": "slope-intercept", "kind": "posterior-fixed-a"}


# ------------------------------------------------------------------ ItemPrior
def test_prior_accepts_exactly_one_pair() -> None:
    assert ItemPrior(mu_b=0.0, sd_b=1.0).payload() == {"mu_b": 0.0, "sd_b": 1.0}
    assert ItemPrior(mu_d=-0.5, sd_d=0.8).payload() == {"mu_d": -0.5, "sd_d": 0.8}
    with pytest.raises(ValidationError, match="exactly one"):
        ItemPrior()
    with pytest.raises(ValidationError, match="exactly one"):
        ItemPrior(mu_b=0.0, sd_b=1.0, mu_d=0.0, sd_d=1.0)
    with pytest.raises(ValidationError, match="exactly one"):
        ItemPrior(mu_b=0.0)  # incomplete pair
    with pytest.raises(ValidationError, match="sd must be"):
        ItemPrior(mu_b=0.0, sd_b=0.0)


# ---------------------------------------------------------------- update_item
def test_update_item_posts_prior_and_parses(fake_service) -> None:
    # numbers from the live stack smoke (2026-07-09): exact se map held over HTTP
    calls = fake_service(
        {
            "a": 1.2,
            "d": 0.1815,
            "se_d": 0.6758684570063347,
            "b": -0.15125,
            "se_b": 0.5632237141719456,
            "n_responses": 8,
            "metric": METRIC,
        }
    )
    out = update_item(
        1.2,
        [ScoredResponse(theta=0.5, u=1), ScoredResponse(theta=-0.5, u=0)],
        prior=ItemPrior(mu_b=0.0, sd_b=1.0),
    )
    assert calls["url"].endswith("/update-item")
    assert calls["payload"]["prior"] == {"mu_b": 0.0, "sd_b": 1.0}
    assert calls["payload"]["a"] == 1.2
    # exact fixed-a SE map survives the parse
    assert out.se_b == pytest.approx(out.se_d / out.a, abs=1e-12)
    assert out.metric["kind"] == "posterior-fixed-a"


def test_update_item_prior_is_required_by_signature() -> None:
    with pytest.raises(TypeError):
        update_item(1.2, [ScoredResponse(theta=0.0, u=1)])  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="a > 0"):
        update_item(
            0.0, [ScoredResponse(theta=0.0, u=1)], prior=ItemPrior(mu_b=0, sd_b=1)
        )


# ------------------------------------------------------------------ calibrate
def _calibration_body(converged: bool) -> dict:
    return {
        "items": [
            {"item": "it01", "a": 0.965, "d": 0.42, "se_a": 0.14, "se_d": 0.09,
             "var_a": 0.0196, "var_d": 0.0081, "cov_ad": 0.0003},
        ],
        "dropped": ["it99"],
        "convergence": {"converged": converged, "n_persons": 1500, "n_items": 29},
        "metric": {"scaling_d": 1, "form": "slope-intercept", "kind": "calibrated"},
    }


def test_calibrate_surfaces_convergence_and_dropped_first_class(fake_service) -> None:
    calls = fake_service(_calibration_body(converged=False))
    out = calibrate([ResponseRecord(person="p1", item="it01", u=1)])
    assert calls["url"].endswith("/calibrate")
    assert calls["payload"]["itemtype"] == "2PL"
    # converged=False is a RESULT, not an exception — the caller decides
    assert out.converged is False
    assert out.dropped == ["it99"]
    assert out.items[0].cov_ad == 0.0003  # covariance ready for /convert-difficulty
    assert calls["timeout"] >= 600.0  # long solves are normal


def test_service_error_payload_raises(fake_service) -> None:
    fake_service({"error": "responses must have person, item, u"})
    with pytest.raises(AnalysisServiceError, match="person, item, u"):
        calibrate([ResponseRecord(person="p1", item="i", u=1)])


# ---------------------------------------------------------------- score + link
def test_score_and_link_parse(fake_service) -> None:
    fake_service(
        {"theta": 0.4132, "se": 0.9106, "n_items": 1, "metric": {"scaling_d": 1}}
    )
    s = score_person([ItemParamsIn(item="i1", a=1.0, d=0.0)], [{"item": "i1", "u": 1}])
    assert s.theta == pytest.approx(0.4132)

    fake_service(
        {"n_common": 20, "r_a": 1.0, "r_d": 0.999, "r_b": 0.9999,
         "mean_shift_b": -0.5, "sd_ratio_b": 1.0, "metric": {"scaling_d": 1}}
    )
    lk = link(
        [ItemParamsIn(item="i1", a=1.0, d=0.0)],
        [ItemParamsIn(item="i1", a=1.0, d=0.5)],
    )
    assert lk.mean_shift_b == pytest.approx(-0.5)


# ------------------------------------------------------------- PoolKind seam
def test_posterior_fixed_a_round_trips_require_metric() -> None:
    m = require_metric(
        {"scaling_d": 1.0, "form": "slope_intercept", "kind": "posterior-fixed-a"},
        where="test",
    )
    assert m.kind == "posterior-fixed-a"
