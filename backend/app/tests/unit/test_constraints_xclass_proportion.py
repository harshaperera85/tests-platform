"""Cross-classified (content × cognitive) and proportion content constraints."""

from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

from app.assembly import assemble, compile_blueprint
from app.schemas.blueprint import Blueprint, ContentConstraint, TIFTarget


def _target() -> TIFTarget:
    return TIFTarget(theta_points=[-1, 0, 1], target_info=[6, 8, 6])


def test_marginal_still_works(default_pool) -> None:
    c = ContentConstraint(tag_type="KC", tag_value="algebra", minimum=3)
    assert c.predicates == {"KC": "algebra"}
    assert c.resolved_minimum(20) == 3


def test_cross_classified_cell_predicates() -> None:
    c = ContentConstraint(tags={"KC": "algebra", "Bloom": "apply"}, minimum=2)
    assert c.predicates == {"KC": "algebra", "Bloom": "apply"}
    assert "KC=algebra" in c.key and "Bloom=apply" in c.key


def test_proportion_resolves_to_count() -> None:
    c = ContentConstraint(
        tag_type="KC", tag_value="algebra", minimum=0.3, mode="proportion"
    )
    assert c.resolved_minimum(20) == 6  # 0.3 * 20
    assert c.resolved_minimum(10) == 3


def test_proportion_bounds_validated() -> None:
    with pytest.raises(ValidationError):
        ContentConstraint(
            tag_type="KC", tag_value="algebra", minimum=1.5, mode="proportion"
        )
    with pytest.raises(ValidationError):
        ContentConstraint(
            tag_type="KC", tag_value="algebra", minimum=2.5
        )  # count must be whole


def test_assemble_satisfies_cross_classified_cell() -> None:
    pool = compile_blueprint  # noqa: F841 (import sanity)
    from app.psychometrics.bank import load_pool

    bank = load_pool("app/psychometrics/fixtures/demo_bank.json")
    bp = Blueprint(
        name="cell",
        length=24,
        statistical_target=_target(),
        content_constraints=[
            # cross-classified: algebra AND apply
            ContentConstraint(tags={"KC": "algebra", "Bloom": "apply"}, minimum=3),
            # plus a marginal on a different dimension
            ContentConstraint(tag_type="Bloom", tag_value="analyze", minimum=4),
        ],
    )
    r = assemble(bp, bank, strategy="mip", time_limit_s=8)
    assert r.feasible
    items = bank.subset(r.forms[0].item_ids)
    algebra_apply = sum(
        1
        for it in items
        if it.tags.get("KC") == "algebra" and it.tags.get("Bloom") == "apply"
    )
    analyze = Counter(it.tags["Bloom"] for it in items)["analyze"]
    assert algebra_apply >= 3
    assert analyze >= 4


def test_assemble_with_proportion_constraint() -> None:
    from app.psychometrics.bank import load_pool

    bank = load_pool("app/psychometrics/fixtures/demo_bank.json")
    bp = Blueprint(
        name="prop",
        length=20,
        statistical_target=_target(),
        content_constraints=[
            ContentConstraint(
                tag_type="domain", tag_value="math", minimum=0.5, mode="proportion"
            ),
        ],
    )
    r = assemble(bp, bank, strategy="mip", time_limit_s=8)
    assert r.feasible
    items = bank.subset(r.forms[0].item_ids)
    math = Counter(it.tags["domain"] for it in items)["math"]
    assert math >= 10  # 0.5 * 20
