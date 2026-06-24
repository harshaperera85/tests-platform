"""Difficulty-view (slope-intercept -> traditional) conversion, SE-aware.

Axis 2 of the metric: the canonical stored form is slope-intercept ``(a, d)``; the
traditional difficulty ``b = -d / a`` is the difficulty *view*. Conversion is routed
by the pool's declared ``kind``:

* **synthetic** (point estimates, no SEs): Python computes ``b = -d/a``; ``se_b`` is
  left ``None``. Python never fabricates ``se_b`` from a one-variable rule.
* **calibrated** (carries parameter covariance): the AUTHORITATIVE ``b`` + ``se_b``
  come from the R/mirt service (``/convert-difficulty``), which computes them with
  **mirt's own delta method** (``mirt::DeltaMethod`` on ``b = -d/a`` with the given
  covariance). A build-time tripwire asserts this equals mirt's ``coef(IRTpars=TRUE)``
  and an independent analytic Jacobian (``convert_difficulty_selftest.R``).
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from app.core.config import settings
from app.psychometrics.params import ItemParameters


@dataclass(frozen=True)
class DifficultyView:
    a: float
    b: float
    se_b: float | None


def synthetic_difficulty(item: ItemParameters) -> DifficultyView:
    """Point-estimate difficulty for a synthetic item: ``b = -d/a``, no SE."""
    return DifficultyView(a=item.a, b=item.b, se_b=None)


def calibrated_difficulty(
    a: float,
    d: float,
    var_a: float,
    var_d: float,
    cov_ad: float = 0.0,
    base_url: str | None = None,
    timeout: float = 10.0,
) -> DifficultyView:
    """Authoritative difficulty + propagated SE(b) via the R/mirt service."""
    url = (base_url or settings.scoring_r_url).rstrip("/") + "/convert-difficulty"
    payload = json.dumps(
        {"a": a, "d": d, "var_a": var_a, "var_d": var_d, "cov_ad": cov_ad}
    ).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"content-type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted)
        out = json.loads(resp.read())
    if "error" in out:
        raise RuntimeError(f"scoring-r convert-difficulty: {out['error']}")
    return DifficultyView(a=out["a"], b=out["b"], se_b=out.get("se_b"))


def difficulty_view(item: ItemParameters, kind: str) -> DifficultyView:
    """Route difficulty conversion by pool kind (synthetic vs calibrated)."""
    if kind == "calibrated":
        if item.se_a is None or item.se_d is None:
            raise ValueError(
                "calibrated difficulty conversion requires se_a and se_d "
                "(and cov_ad); refusing to fabricate SE(b)."
            )
        return calibrated_difficulty(
            item.a, item.d, item.se_a**2, item.se_d**2, item.cov_ad or 0.0
        )
    return synthetic_difficulty(item)
