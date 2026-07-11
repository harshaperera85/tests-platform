"""``loft`` — linear-on-the-fly administration (BP-MODES-1 §4).

A unique conforming form is assembled **per examinee at session start** (via the
owned §4 assembly service), then delivered and scored exactly like a fixed form:
sequential order, EAP on the canonical metric. What distinguishes LOFT from
``linear`` is *when* assembly happens (session start, seeded per session) and the
§4.1/§4.2 acceptance semantics — the §4.4 conformance record is built at
initialization and carried in the session state (``blueprint_conformant`` is true
by construction; a failed assembly fails the session start, per §4.3).

Per CLAUDE.md golden rule 1 this file is fully self-contained: it implements the
six contract methods and registers itself, touching neither the engine core, the
registry, the contract, nor any sibling strategy.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.assembly.loft import PoolFormRef, assemble_loft_session
from app.engine.contract import (
    AdministrationStrategy,
    Navigation,
    NextAction,
    ScoreResult,
    SessionState,
    TerminationDecision,
)
from app.engine.registry import register
from app.engine.strategies.delivery import apply_delivery, session_seed
from app.psychometrics.bank import ItemPool, load_default_pool
from app.psychometrics.params import ItemParameters
from app.psychometrics.scoring import eap_estimate
from app.schemas.test_config import LoftConfig


@register
class LoftStrategy(AdministrationStrategy):
    model_type = "loft"
    config_schema = LoftConfig

    # ------------------------------------------------------------------ init
    def initialize(
        self, config: BaseModel, pool_ref: Any, context: dict[str, Any]
    ) -> SessionState:
        """Assemble THIS session's conforming form (§4.3), then start at 0.

        Context: ``blueprint`` (required — LOFT always assembles per session),
        ``session_id``, optional ``seed`` (defaults to a stable hash of the
        session id), optional ``usage_counts`` + ``n_prior_sessions`` for the
        §4.2 running exposure-rate mask (supplied by the session layer).
        Engine (c) additionally needs ``form_pool`` (the published, reviewed
        candidates as ``{form_id, item_ids}`` dicts) and optionally
        ``draw_counts`` (per-form draws so far, for rotation).
        """
        cfg = config if isinstance(config, LoftConfig) else LoftConfig()
        pool: ItemPool = (
            pool_ref if isinstance(pool_ref, ItemPool) else load_default_pool()
        )
        blueprint = context.get("blueprint")
        if blueprint is None:
            raise ValueError(
                "LoftStrategy.initialize needs context['blueprint'] — LOFT "
                "assembles a unique form per session; there is no pre-assembled "
                "form path"
            )
        session_id = str(context.get("session_id", "loft-session"))
        seed = session_seed(context, session_id)

        raw_pool = context.get("form_pool")
        form_pool = (
            [
                PoolFormRef(
                    form_id=str(f["form_id"]), item_ids=tuple(f["item_ids"])
                )
                for f in raw_pool
            ]
            if raw_pool is not None
            else None
        )
        form = assemble_loft_session(
            blueprint,
            pool,
            engine=cfg.engine,
            seed=int(seed),
            usage_counts=context.get("usage_counts"),
            n_prior_sessions=int(context.get("n_prior_sessions", 0)),
            max_attempts=cfg.max_attempts,
            time_limit_s=cfg.time_limit_s,
            form_pool=form_pool,
            draw_counts=context.get("draw_counts"),
        )
        # G5 delivery options: seeded order randomization + pretest embedding.
        # The §4.4 record stays about the OPERATIONAL form; delivery facts ride
        # alongside it.
        order, pretest_ids = apply_delivery(
            list(form.item_ids), cfg.delivery, int(seed)
        )
        record = dict(form.record)
        record["delivery"] = {
            "randomized": cfg.delivery.randomize_item_order,
            "n_pretest": len(pretest_ids),
        }

        params = pool.subset(form.item_ids)
        return SessionState(
            model_type=self.model_type,
            session_id=session_id,
            position=0,
            completed=False,
            data={
                "item_ids": order,
                "item_params": {p.item_id: _dump_params(p) for p in params},
                "pretest_item_ids": pretest_ids,
                "delivery_seed": int(seed),
                "responses": {},
                "conformance_record": record,
                "assembly_warnings": form.warnings,
                "navigation": cfg.navigation.model_dump(),
                "scoring_method": cfg.scoring.method,
            },
        )

    # ------------------------------------------------------------- next step
    def next_action(self, state: SessionState) -> NextAction:
        item_ids: list[str] = state.data["item_ids"]
        if state.position >= len(item_ids):
            return NextAction(kind="complete", navigation=self.capabilities(state))
        return NextAction(
            kind="present",
            payload={
                "item_id": item_ids[state.position],
                "position": state.position,
                "total_items": len(item_ids),
            },
            navigation=self.capabilities(state),
        )

    def record_response(self, state: SessionState, response: Any) -> SessionState:
        item_ids: list[str] = state.data["item_ids"]
        new = state.model_copy(deep=True)
        item_id, value = _parse_response(response, item_ids, state.position)
        if item_id not in state.data["item_params"] and item_id not in set(
            state.data.get("pretest_item_ids", [])
        ):
            raise ValueError(f"response references unknown item {item_id!r}")
        new.data["responses"][item_id] = value
        new.position = state.position + 1
        new.completed = new.position >= len(item_ids)
        return new

    def is_complete(self, state: SessionState) -> TerminationDecision:
        total = len(state.data["item_ids"])
        if state.position >= total:
            return TerminationDecision(complete=True, reason="end_of_form")
        return TerminationDecision(complete=False)

    # ----------------------------------------------------------------- score
    def score(self, state: SessionState) -> ScoreResult:
        """EAP theta on the canonical metric over the answered OPERATIONAL
        items — embedded pretest items are unscored (G5)."""
        item_ids: list[str] = state.data["item_ids"]
        responses: dict[str, int] = state.data["responses"]
        params: dict[str, Any] = state.data["item_params"]
        answered = [iid for iid in item_ids if iid in responses and iid in params]
        items = [_load_params(params[iid]) for iid in answered]
        values = [responses[iid] for iid in answered]
        est = eap_estimate(items, values)
        return ScoreResult(
            theta=est.theta,
            standard_error=est.standard_error,
            scale="canonical",
            detail={
                "method": est.method,
                "n_answered": len(answered),
                "n_items": len(item_ids),
                "n_pretest": len(state.data.get("pretest_item_ids", [])),
                "blueprint_conformant": state.data["conformance_record"][
                    "blueprint_conformant"
                ],
            },
        )

    # ---------------------------------------------------------- capabilities
    def capabilities(self, state: SessionState | None = None) -> Navigation:
        nav = (state.data.get("navigation") if state else None) or {}
        total = len(state.data["item_ids"]) if state else None
        return Navigation(
            can_review=nav.get("can_review", True),
            can_skip=nav.get("can_skip", False),
            can_navigate_back=nav.get("can_navigate_back", True),
            fixed_length=True,
            total_items=total,
        )


# --------------------------------------------------------------------- helpers
def _dump_params(p: ItemParameters) -> dict[str, float]:
    return {"a": p.a, "d": p.d, "c": p.c, "u": p.u, "scaling_d": p.scaling_d}


def _load_params(d: dict[str, Any]) -> ItemParameters:
    return ItemParameters(
        item_id=d.get("item_id", "x"),
        a=d["a"],
        d=d["d"],
        c=d.get("c", 0.0),
        u=d.get("u", 1.0),
        scaling_d=d["scaling_d"],
    )


def _parse_response(
    response: Any, item_ids: list[str], position: int
) -> tuple[str, int]:
    current = item_ids[position] if position < len(item_ids) else None
    if isinstance(response, dict):
        item_id = response.get("item_id") or current
        raw = response.get("correct", response.get("response", response.get("u")))
    else:
        item_id, raw = current, response
    if item_id is None:
        raise ValueError("cannot determine item_id for response")
    if raw is None:
        raise ValueError("response is missing a correctness value")
    value = int(raw)
    if value not in (0, 1):
        raise ValueError(f"response must be 0 or 1, got {raw!r}")
    return item_id, value
