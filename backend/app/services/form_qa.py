"""Form-QA report — what reviewers see at each lifecycle gate.

Generated server-side from the stored form + pool + blueprint, on the canonical
**logistic D=1 slope-intercept** metric (reuses ``psychometrics``). Model-agnostic:
operates on an assembled form regardless of how it was assembled.

Contents: the answer key (in form order), key-balance distribution (with an
imbalance flag), content coverage vs the blueprint, and a psychometric summary —
the conditional SE curve ``SE(θ)=1/√I(θ)``, the test characteristic curve
``TCC(θ)=Σ Pᵢ(θ)``, marginal reliability, and the actual-vs-target TIF.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.models.blueprint import BlueprintRow
from app.models.form import FormRow
from app.psychometrics import pools
from app.psychometrics.information import (
    prob_correct,
    standard_error,
    test_information,
)
from app.psychometrics.scoring import _quadrature
from app.schemas.blueprint import Blueprint
from app.schemas.governance import (
    AnswerKeyEntry,
    CoverageRow,
    FormQAReport,
    KeyBalance,
    QAPsychometricPoint,
    TIFActualTarget,
)

#: θ grid for the SE / TCC / information curves.
_THETA_GRID = [round(-3.0 + 0.5 * i, 3) for i in range(13)]  # -3 … 3


def _key_balance(keys: list[str | None]) -> KeyBalance:
    present = [k for k in keys if k]
    counts = dict(sorted(Counter(present).items()))
    n = len(present)
    # Flag if any single option carries > 40% of keyed items (positional bias), or
    # an option seen in the bank is entirely absent from the form.
    imbalanced = False
    note = "balanced"
    if n:
        top = max(counts.values())
        if top / n > 0.40:
            imbalanced = True
            note = f"one option holds {top}/{n} keys (>40%)"
    if not present:
        note = "no answer keys on these items"
    return KeyBalance(counts=counts, n=n, imbalanced=imbalanced, note=note)


def build_qa_report(db: Session, form: FormRow) -> FormQAReport:
    bp_row = db.get(BlueprintRow, form.blueprint_id)
    blueprint = Blueprint.model_validate(bp_row.spec) if bp_row else None

    doc = pools.load_document_by_id(form.pool_id)
    keys_by_id = {it["item_id"]: it.get("answer_key") for it in doc["items"]}
    pool = pools.load_pool_by_id(form.pool_id)
    items = pool.subset(form.item_ids)  # canonical params + tags, in form order

    # answer key + balance
    answer_key = [
        AnswerKeyEntry(position=i + 1, item_id=iid, answer_key=keys_by_id.get(iid))
        for i, iid in enumerate(form.item_ids)
    ]
    key_balance = _key_balance([keys_by_id.get(iid) for iid in form.item_ids])

    # content coverage vs blueprint (reuse the constraint predicates)
    coverage: list[CoverageRow] = []
    length = len(form.item_ids)
    for c in blueprint.content_constraints if blueprint else []:
        preds = c.predicates
        count = sum(
            1 for it in items if all(it.tags.get(k) == v for k, v in preds.items())
        )
        mn = c.resolved_minimum(length)
        mx = c.resolved_maximum(length)
        coverage.append(
            CoverageRow(
                label=c.key,
                count=count,
                minimum=mn,
                maximum=mx,
                satisfied=(mn is None or count >= mn) and (mx is None or count <= mx),
            )
        )

    # psychometric curves on the canonical metric
    curve: list[QAPsychometricPoint] = []
    for theta in _THETA_GRID:
        info = test_information(items, theta)
        se = standard_error(info)
        tcc = sum(prob_correct(it, theta) for it in items)
        curve.append(
            QAPsychometricPoint(
                theta=theta,
                information=info,
                se=None if se == float("inf") else se,
                tcc=tcc,
            )
        )

    # marginal reliability: 1 - E_φ[1/I(θ)] over a standard-normal prior (σ²=1)
    nodes, weights = _quadrature(41, -4.0, 4.0)
    err_var = 0.0
    for theta, w in zip(nodes, weights, strict=True):
        info = test_information(items, theta)
        err_var += w * (1.0 / info if info > 1e-9 else 1e6)
    marginal_reliability = max(0.0, min(1.0, 1.0 - err_var))

    # actual vs target TIF (at the blueprint θ points). Content-only blueprints
    # (BP-MODES-1 A1) carry no target, so there is nothing to compare against.
    tif: list[TIFActualTarget] = []
    if blueprint and blueprint.statistical_target is not None:
        t = blueprint.statistical_target
        for theta, tgt, actual in zip(
            t.theta_points, t.target_info, form.tif_actual, strict=False
        ):
            tif.append(TIFActualTarget(theta=theta, target=tgt, actual=actual))

    return FormQAReport(
        form_id=form.id,
        lifecycle_state=form.lifecycle_state,
        n_items=length,
        answer_key=answer_key,
        key_balance=key_balance,
        coverage=coverage,
        curve=curve,
        marginal_reliability=marginal_reliability,
        tif_actual_vs_target=tif,
    )
