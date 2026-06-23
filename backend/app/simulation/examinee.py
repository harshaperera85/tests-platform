"""Simulate a linear session for an examinee at a known true theta.

Drives the registered ``LinearStrategy`` through the engine contract
(``initialize`` → ``next_action`` → ``record_response`` → ``score``), generating
each response from the canonical 2PL probability at the true theta (seeded, so runs
are reproducible). After each response it re-scores, yielding a theta/SE trace that
shows estimates converging toward the true value — a genuine simulated end-to-end
demonstration. Pure capability: no engine/assembly/contract changes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.engine import registry
from app.psychometrics.bank import ItemPool
from app.psychometrics.information import prob_correct
from app.schemas.test_config import LinearConfig


@dataclass(frozen=True)
class SimulationStep:
    position: int
    item_id: str
    prob_correct: float
    response: int
    theta: float | None
    standard_error: float | None


@dataclass(frozen=True)
class SimulationResult:
    true_theta: float
    seed: int
    n_items: int
    final_theta: float | None
    final_standard_error: float | None
    trace: list[SimulationStep]


def simulate_linear(
    pool: ItemPool,
    item_ids: list[str],
    true_theta: float,
    *,
    seed: int = 0,
) -> SimulationResult:
    """Walk a pre-assembled linear form as an examinee at ``true_theta``."""
    rng = random.Random(seed)
    strategy = registry.get_strategy("linear")
    state = strategy.initialize(
        LinearConfig(), pool, {"form_item_ids": item_ids, "session_id": "sim"}
    )

    trace: list[SimulationStep] = []
    while not strategy.is_complete(state).complete:
        action = strategy.next_action(state)
        if action.kind != "present":
            break
        item_id = str(action.payload["item_id"])
        p = prob_correct(pool.get(item_id), true_theta)
        response = 1 if rng.random() < p else 0
        state = strategy.record_response(
            state, {"item_id": item_id, "correct": response}
        )
        est = strategy.score(state)
        trace.append(
            SimulationStep(
                position=state.position,
                item_id=item_id,
                prob_correct=p,
                response=response,
                theta=est.theta,
                standard_error=est.standard_error,
            )
        )

    final = strategy.score(state)
    return SimulationResult(
        true_theta=true_theta,
        seed=seed,
        n_items=len(item_ids),
        final_theta=final.theta,
        final_standard_error=final.standard_error,
        trace=trace,
    )
