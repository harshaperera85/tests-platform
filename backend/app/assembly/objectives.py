"""TIF objectives for the assembly MIP (plan §6).

Separated from the constraint builder (:mod:`app.assembly.ata_model`) so the
objective family is swappable. v1 ships the two classical forms; the cutting-edge
extensions noted in the plan (robust ATA, chance-constrained ATA, bidirectional
exposure) slot in here later as additional ``add_*_objective`` functions without
disturbing callers.

- **minimax**: minimize the worst-point absolute miss ``max_{f,k} |TIF_fk - target_k|``.
  Drives every form's information curve onto the target. Default for parallel forms.
- **maximin**: maximize the worst-point information ``min_{f,k} TIF_fk``. Pushes
  information as high as possible where the form is weakest (``target_info`` is then
  a reference curve for reporting rather than a ceiling).

A ``tolerance`` on the blueprint additionally pins hard ``|TIF - target| <= tol``
bands (applied here for minimax, the form where a band is meaningful).
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from app.assembly.ata_model import INFO_SCALE, AtaModel

#: Integer scale for per-theta minimax weights (CP-SAT is integer-only).
WEIGHT_SCALE = 1000


def _weights_are_unit(weights: tuple[float, ...] | None, n: int) -> bool:
    """True when weights are absent or all exactly 1.0 (the default minimax)."""
    if not weights:
        return True
    return len(weights) == n and all(w == 1.0 for w in weights)


def _underuse_penalty(am: AtaModel, value_scale: int) -> cp_model.LinearExpr | None:
    """Under-use bias term (in objective ``value_scale`` units), or ``None`` when off.

    Sums each selected item's cumulative exposure times the user weight, so the
    solver prefers under-utilized items. Returns ``None`` when disabled so callers
    minimize/maximize the bare objective var — keeping default assembly byte-for-byte
    identical.
    """
    p = am.problem
    if p.underuse_weight <= 0.0 or not p.exposure:
        return None
    coeffs: list[int] = []
    vars_: list[cp_model.IntVar] = []
    for f in range(p.num_forms):
        for i in range(p.n_items):
            c = round(p.underuse_weight * value_scale * p.exposure[i])
            if c:
                coeffs.append(c)
                vars_.append(am.x[(i, f)])
    if not vars_:
        return None
    return cp_model.LinearExpr.weighted_sum(vars_, coeffs)


def add_minimax_objective(am: AtaModel) -> tuple[cp_model.IntVar, int]:
    """Add the (optionally weighted) minimax deviation objective.

    Returns ``(objective_var, value_scale)``; divide ``var`` by ``value_scale`` to
    get the reported objective in information units. Minimizes
    ``max_{f,k} w_k·|TIF_fk − target_k|`` (``w_k`` default 1.0). With all-unit
    weights this is the exact unweighted minimax (identical CP-SAT model).
    """
    m = am.model
    p = am.problem
    n_k = len(p.theta_points)
    max_info = sum(max(row) for row in am.scaled_info) or 1
    ub = max(max_info, max(am.scaled_target, default=0)) + 1
    tol_scaled = round(p.tolerance * INFO_SCALE) if p.tolerance is not None else None

    if _weights_are_unit(p.weights, n_k):
        # Unweighted path — byte-for-byte the original model.
        y = m.new_int_var(0, ub, "minimax_dev")
        for f in range(p.num_forms):
            for k in range(n_k):
                dev = am.form_info[f][k] - am.scaled_target[k]
                m.add(y >= dev)
                m.add(y >= -dev)
                if tol_scaled is not None:
                    m.add(dev <= tol_scaled)
                    m.add(-dev <= tol_scaled)
        pen = _underuse_penalty(am, INFO_SCALE)
        m.minimize(y if pen is None else y + pen)
        return y, INFO_SCALE

    # Weighted path: y >= w_int_k · dev (integer-scaled weights). The objective is in
    # INFO_SCALE·WEIGHT_SCALE units; the tolerance band stays on the raw (unweighted)
    # deviation since it is an absolute info band.
    w_int = [round(w * WEIGHT_SCALE) for w in p.weights]
    # y bounds w_int_k * |dev|; |dev| <= ub, so the cap is ub * max weight.
    y = m.new_int_var(0, ub * (max(w_int) or 1) + 1, "wminimax_dev")
    for f in range(p.num_forms):
        for k in range(n_k):
            dev = am.form_info[f][k] - am.scaled_target[k]
            m.add(y >= w_int[k] * dev)
            m.add(y >= -w_int[k] * dev)
            if tol_scaled is not None:
                m.add(dev <= tol_scaled)
                m.add(-dev <= tol_scaled)
    scale = INFO_SCALE * WEIGHT_SCALE
    pen = _underuse_penalty(am, scale)
    m.minimize(y if pen is None else y + pen)
    return y, scale


def add_maximin_objective(am: AtaModel) -> tuple[cp_model.IntVar, int]:
    """Add the maximin information objective; return ``(floor_var, value_scale)``."""
    m = am.model
    p = am.problem
    ub = (sum(max(row) for row in am.scaled_info) or 1) + 1
    t = m.new_int_var(0, ub, "maximin_info")
    for f in range(p.num_forms):
        for k in range(len(p.theta_points)):
            m.add(t <= am.form_info[f][k])
    # maximize the floor, biased toward under-utilized items (penalty subtracted).
    pen = _underuse_penalty(am, INFO_SCALE)
    m.maximize(t if pen is None else t - pen)
    return t, INFO_SCALE
