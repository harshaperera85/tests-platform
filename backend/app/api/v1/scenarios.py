"""Named demo scenarios (plan §10 — drive the workflow with curated examples).

Each scenario pairs a simulated pool with a blueprint preset that exercises one
capability of the linear workflow, so the UI can load it in one click and the
walkthrough can demonstrate each behavior deliberately. Read-only and static.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.blueprint import (
    Blueprint,
    ContentConstraint,
    ExposureTarget,
    TIFTarget,
)
from app.schemas.responses import ScenarioRead

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_SCENARIOS: list[ScenarioRead] = [
    ScenarioRead(
        scenario_id="smoke_small",
        title="Smoke test (small 2PL bank)",
        description="The minimal 48-item bank with a centered TIF target.",
        pool_id="small_2pl",
        blueprint=Blueprint(
            name="linear-demo",
            length=20,
            statistical_target=TIFTarget(
                theta_points=[-1, 0, 1], target_info=[7, 9, 7], method="minimax"
            ),
            content_constraints=[
                ContentConstraint(
                    tag_type="KC", tag_value="algebra", minimum=4, maximum=8
                ),
                ContentConstraint(tag_type="KC", tag_value="geometry", minimum=4),
                ContentConstraint(tag_type="Bloom", tag_value="analyze", minimum=3),
            ],
        ),
        note="Baseline: actual TIF should sit on 7/9/7 (D=1); assembles instantly.",
    ),
    ScenarioRead(
        scenario_id="multi_domain",
        title="Multi-domain content balance",
        description="Equal coverage across math / science / ela on the mixed bank.",
        pool_id="demo_mixed",
        blueprint=Blueprint(
            name="multi-domain-balance",
            length=30,
            statistical_target=TIFTarget(
                theta_points=[-1, 0, 1], target_info=[12, 13, 12], method="minimax"
            ),
            content_constraints=[
                ContentConstraint(
                    tag_type="domain", tag_value="math", minimum=10, maximum=10
                ),
                ContentConstraint(
                    tag_type="domain", tag_value="science", minimum=10, maximum=10
                ),
                ContentConstraint(
                    tag_type="domain", tag_value="ela", minimum=10, maximum=10
                ),
            ],
        ),
        note="Preview should show all three domain badges ✓ at exactly 10 each.",
    ),
    ScenarioRead(
        scenario_id="mastery_cut",
        title="Mastery cut score (maximin @ θ=1.5)",
        description="Maximize information at a high cut score (pass/fail point).",
        pool_id="demo_mixed",
        blueprint=Blueprint(
            name="mastery-cut",
            length=25,
            statistical_target=TIFTarget(
                theta_points=[1.5], target_info=[14], method="maximin"
            ),
        ),
        note="Information should peak near θ=1.5; the bank has plenty of hard items.",
    ),
    ScenarioRead(
        scenario_id="parallel_exposure",
        title="Parallel forms with exposure control",
        description="Three parallel forms with each item used at most once.",
        pool_id="demo_mixed",
        blueprint=Blueprint(
            name="parallel-exposure",
            length=30,
            num_forms=3,
            statistical_target=TIFTarget(
                theta_points=[-1, 0, 1], target_info=[8, 9, 8], method="minimax"
            ),
            exposure_target=ExposureTarget(max_use_per_item=1),
        ),
        note="Three parallel forms, zero item overlap (90 of 252 items used).",
    ),
    ScenarioRead(
        scenario_id="guessing_3pl",
        title="3PL pool (guessing)",
        description="Reasoning-heavy form drawn from the bank's 3PL (c>0) items.",
        pool_id="demo_mixed",
        blueprint=Blueprint(
            name="guessing-3pl",
            length=25,
            statistical_target=TIFTarget(
                theta_points=[-0.5, 0.5, 1.5], target_info=[9, 10, 9], method="minimax"
            ),
            content_constraints=[
                ContentConstraint(tag_type="TIMSS", tag_value="reasoning", minimum=8),
            ],
        ),
        note="Exercises the 3PL information path; info is lower per item than 2PL.",
    ),
    ScenarioRead(
        scenario_id="infeasible_demo",
        title="Infeasible (over-constrained)",
        description="Demands more algebra items than exist — shows the failure path.",
        pool_id="small_2pl",
        blueprint=Blueprint(
            name="infeasible-demo",
            length=20,
            statistical_target=TIFTarget(theta_points=[0], target_info=[5]),
            content_constraints=[
                ContentConstraint(
                    tag_type="KC", tag_value="algebra", minimum=20, maximum=20
                ),
            ],
        ),
        note="Expect a clear 'infeasible' message, not a crash (12 algebra items).",
    ),
]


@router.get("", response_model=list[ScenarioRead])
def list_scenarios() -> list[ScenarioRead]:
    return _SCENARIOS
