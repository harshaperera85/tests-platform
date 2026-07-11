"""``linear`` — the linear fixed-form administration model (plan §4, §11 Phase 1).

The first concrete :class:`AdministrationStrategy`. It either loads a pre-assembled
form or assembles one from a blueprint via the owned OR-Tools engine, then walks the
test-taker sequentially through the fixed item order and scores the result on the
canonical theta metric (EAP) through the psychometrics layer.

Per CLAUDE.md golden rule 1 this file is fully self-contained: it implements the six
contract methods and registers itself. It does not touch the engine core, the
registry, the contract, or any sibling strategy — the only "edit" is the
``@register`` decoration, which is the sanctioned extension point.

Session state is kept JSON-serializable (item ids, canonical item parameters, and
responses live in ``SessionState.data``) so a session can be persisted, audited, and
scored without holding a live pool reference.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.assembly import assemble
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
from app.schemas.test_config import LinearConfig


@register
class LinearStrategy(AdministrationStrategy):
    model_type = "linear"
    config_schema = LinearConfig

    # ------------------------------------------------------------------ init
    def initialize(
        self, config: BaseModel, pool_ref: Any, context: dict[str, Any]
    ) -> SessionState:
        """Resolve the form's items, then start the session at position 0.

        Item source, in priority order:
        1. ``context["form_item_ids"]`` — a pre-assembled form's ordered ids.
        2. ``context["blueprint"]`` — assemble now via the OR-Tools engine.

        ``pool_ref`` is an :class:`ItemPool`; the fixture pool is used if omitted.
        """
        cfg = config if isinstance(config, LinearConfig) else LinearConfig()
        pool: ItemPool = (
            pool_ref if isinstance(pool_ref, ItemPool) else load_default_pool()
        )

        item_ids = self._resolve_item_ids(cfg, pool, context)
        if not item_ids:
            raise ValueError(
                "LinearStrategy.initialize needs context['form_item_ids'] or "
                "context['blueprint'] to determine the form"
            )

        session_id = str(context.get("session_id", "linear-session"))
        # G5 delivery options: seeded order randomization + pretest embedding.
        # Defaults leave the assembled order byte-for-byte unchanged.
        seed = session_seed(context, session_id)
        order, pretest_ids = apply_delivery(list(item_ids), cfg.delivery, seed)

        params = pool.subset(item_ids)
        return SessionState(
            model_type=self.model_type,
            session_id=session_id,
            position=0,
            completed=False,
            data={
                "item_ids": order,
                "item_params": {p.item_id: _dump_params(p) for p in params},
                "pretest_item_ids": pretest_ids,
                "delivery_seed": seed,
                "responses": {},
                "navigation": cfg.navigation.model_dump(),
                "scoring_method": cfg.scoring.method,
            },
        )

    def _resolve_item_ids(
        self, cfg: LinearConfig, pool: ItemPool, context: dict[str, Any]
    ) -> list[str]:
        if context.get("form_item_ids"):
            return list(context["form_item_ids"])
        blueprint = context.get("blueprint")
        if blueprint is not None:
            strategy = context.get("assembly_strategy", "mip")
            result = assemble(blueprint, pool, strategy=strategy)
            if not result.feasible or not result.forms:
                raise ValueError(
                    f"assembly for linear form was {result.status}; cannot initialize"
                )
            return list(result.forms[0].item_ids)
        return []

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
        """Record one response and advance. ``response`` is a dict with an item id
        and a 0/1 correctness; the item defaults to the current position's item."""
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
        items, in order — embedded pretest items are unscored (G5)."""
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
    # Canonical slope-intercept (a, d); b is the derived difficulty view.
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
