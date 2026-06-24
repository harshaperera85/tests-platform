"""The enforced metric contract + native fixture consistency."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.psychometrics.bank import load_pool
from app.psychometrics.params import require_metric


def test_undeclared_metric_raises(tmp_path: Path) -> None:
    bad = tmp_path / "no_metric.json"
    bad.write_text(json.dumps({"items": [{"item_id": "z", "a": 1.0, "d": 0.0}]}))
    with pytest.raises(ValueError, match="declared metric"):
        load_pool(bad)


def test_partial_metric_raises() -> None:
    with pytest.raises(ValueError, match="missing required keys"):
        require_metric({"scaling_d": 1.0}, where="t")  # no form / kind


def test_fixtures_native_d1_slope_intercept_and_b_consistent() -> None:
    for name in ("small_2pl_bank.json", "demo_bank.json"):
        pool = load_pool(Path("app/psychometrics/fixtures") / name)
        assert pool.metric is not None
        assert pool.metric.scaling_d == 1.0
        assert pool.metric.form == "slope_intercept"
        assert pool.metric.kind == "synthetic"
        for it in pool.items:
            assert it.scaling_d == 1.0
            assert it.b == pytest.approx(-it.d / it.a)
            assert it.se_b is None  # synthetic: no fabricated SE
