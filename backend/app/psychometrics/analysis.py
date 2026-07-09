"""Analysis-module client — response-based IRT estimation via scoring-r (P2).

Typed, **stateless** wrappers for the four estimation endpoints seeded by the
`p2-analysis-module-seed` PR: ``/calibrate`` (joint 2PL MML-EM), ``/score`` (EAP
under fixed params), ``/update-item`` (fixed-a grid posterior over ``d`` — the
refinement-loop workhorse), and ``/link`` (scale-linking diagnostics). Pattern
follows :mod:`app.psychometrics.difficulty` (urllib + typed models + honest error
surfacing).

Division of labor (pinned with the item-calibration owner, 2026-07-09):

* This client is a **stateless estimator wrapper**. It does NOT read or write bank
  state, fetch priors, decide promotion, or encode the update discipline (original
  prior + ALL accumulated responses, never posterior→prior chaining) — those belong
  to the future write-back orchestrator.
* ``/update-item``'s **prior is a required argument** (``{mu_b, sd_b}`` or
  ``{mu_d, sd_d}``). There is deliberately NO diffuse default: a silently-defaulted
  prior would erase exactly the measured value of the AI priors (30–39%
  responses-to-precision savings — item-calibration Doc 09, 2026-07-07).
* ``/calibrate``'s convergence report and dropped-items list are **first-class
  results**, never exception-swallowed: an R-side ``error`` payload raises
  :class:`AnalysisServiceError`; ``converged: false`` does not — the caller decides
  what non-convergence means.

Everything is on the canonical logistic D=1 slope-intercept metric (golden rule 4);
responses carry the service's metric declaration verbatim.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.config import settings


class AnalysisServiceError(RuntimeError):
    """The scoring-r service reported an error payload (or malformed output)."""


# --------------------------------------------------------------------- inputs
class ResponseRecord(BaseModel):
    """One person × item scored response (u ∈ {0, 1})."""

    person: str
    item: str
    u: int


class ItemParamsIn(BaseModel):
    """Fixed canonical params for scoring/linking inputs."""

    item: str
    a: float
    d: float


class ScoredResponse(BaseModel):
    """One response with the responder's scored ability (for /update-item)."""

    theta: float
    u: int


class ItemPrior(BaseModel):
    """The REQUIRED prior for a fixed-a item update: exactly one of the
    difficulty-view (``mu_b``/``sd_b``) or intercept (``mu_d``/``sd_d``) pairs."""

    model_config = ConfigDict(frozen=True)

    mu_b: float | None = None
    sd_b: float | None = None
    mu_d: float | None = None
    sd_d: float | None = None

    @model_validator(mode="after")
    def _exactly_one_pair(self) -> ItemPrior:
        has_b = self.mu_b is not None and self.sd_b is not None
        has_d = self.mu_d is not None and self.sd_d is not None
        if has_b == has_d:  # neither, or both
            raise ValueError(
                "prior needs exactly one complete pair: {mu_b, sd_b} or {mu_d, sd_d}"
            )
        sd = self.sd_b if has_b else self.sd_d
        if sd is not None and sd <= 0:
            raise ValueError("prior sd must be > 0")
        return self

    def payload(self) -> dict[str, float]:
        if self.mu_b is not None and self.sd_b is not None:
            return {"mu_b": self.mu_b, "sd_b": self.sd_b}
        assert self.mu_d is not None and self.sd_d is not None
        return {"mu_d": self.mu_d, "sd_d": self.sd_d}


# -------------------------------------------------------------------- results
class CalibratedItem(BaseModel):
    item: str
    a: float
    d: float
    se_a: float | None = None
    se_d: float | None = None
    var_a: float | None = None
    var_d: float | None = None
    cov_ad: float | None = None


class ConvergenceReport(BaseModel):
    converged: bool
    n_persons: int
    n_items: int


class CalibrationResult(BaseModel):
    """Joint-calibration output. ``converged`` and ``dropped`` are first-class:
    inspect them before trusting the parameters."""

    items: list[CalibratedItem]
    #: items excluded before fitting (near-degenerate response vectors)
    dropped: list[str]
    convergence: ConvergenceReport
    metric: dict[str, Any]

    @property
    def converged(self) -> bool:
        return self.convergence.converged


class PersonScore(BaseModel):
    theta: float
    se: float
    n_items: int
    metric: dict[str, Any]


class ItemUpdate(BaseModel):
    """Fixed-a posterior update. ``se_b = se_d / a`` exactly (a is a supplied
    constant — a computed posterior, not a propagated approximation)."""

    a: float
    d: float
    se_d: float
    b: float
    se_b: float
    n_responses: int
    metric: dict[str, Any]


class LinkDiagnostics(BaseModel):
    n_common: int
    r_a: float
    r_d: float
    r_b: float
    mean_shift_b: float
    sd_ratio_b: float
    metric: dict[str, Any]


# --------------------------------------------------------------------- client
def _post(
    path: str, payload: dict[str, Any], *, base_url: str | None, timeout: float
) -> dict[str, Any]:
    url = (base_url or settings.scoring_r_url).rstrip("/") + path
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted)
        out = json.loads(resp.read())
    if not isinstance(out, dict):
        raise AnalysisServiceError(f"scoring-r {path}: malformed response")
    if "error" in out:
        raise AnalysisServiceError(f"scoring-r {path}: {out['error']}")
    return out


def calibrate(
    responses: list[ResponseRecord],
    *,
    itemtype: Literal["2PL"] = "2PL",
    base_url: str | None = None,
    timeout: float = 600.0,
) -> CalibrationResult:
    """Joint MML-EM calibration on person-level responses (long format).

    Returns canonical ``(a, d)`` + SEs + covariance elements per item — ready for
    ``/convert-difficulty``'s delta-method b view — plus the honest convergence
    report and the dropped-items list. Long solves are normal: generous timeout.
    """
    out = _post(
        "/calibrate",
        {
            "responses": [r.model_dump() for r in responses],
            "itemtype": itemtype,
        },
        base_url=base_url,
        timeout=timeout,
    )
    return CalibrationResult.model_validate(out)


def score_person(
    params: list[ItemParamsIn],
    responses: list[dict[str, Any]],
    *,
    base_url: str | None = None,
    timeout: float = 30.0,
) -> PersonScore:
    """EAP ability for one person under fixed canonical params.

    ``responses``: ``[{"item": …, "u": 0|1}]`` for the items this person answered.
    """
    out = _post(
        "/score",
        {"params": [p.model_dump() for p in params], "responses": responses},
        base_url=base_url,
        timeout=timeout,
    )
    return PersonScore.model_validate(out)


def update_item(
    a: float,
    responses: list[ScoredResponse],
    prior: ItemPrior,
    *,
    base_url: str | None = None,
    timeout: float = 30.0,
) -> ItemUpdate:
    """Fixed-a grid posterior over ``d`` for ONE item — the refinement-loop
    workhorse. ``prior`` is required by design (see module docstring); ``a`` is
    the caller's responsibility (bank a_prior / regime median — orchestrator
    policy, not decided here)."""
    if a <= 0:
        raise ValueError("update_item requires a > 0")
    out = _post(
        "/update-item",
        {
            "a": a,
            "responses": [r.model_dump() for r in responses],
            "prior": prior.payload(),
        },
        base_url=base_url,
        timeout=timeout,
    )
    return ItemUpdate.model_validate(out)


def link(
    set_x: list[ItemParamsIn],
    set_y: list[ItemParamsIn],
    *,
    base_url: str | None = None,
    timeout: float = 30.0,
) -> LinkDiagnostics:
    """Scale-linking diagnostics between two canonical ``(a, d)`` sets
    (≥ 3 common items required by the service)."""
    out = _post(
        "/link",
        {
            "set_x": [p.model_dump() for p in set_x],
            "set_y": [p.model_dump() for p in set_y],
        },
        base_url=base_url,
        timeout=timeout,
    )
    return LinkDiagnostics.model_validate(out)
