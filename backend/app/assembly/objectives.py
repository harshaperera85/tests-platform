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


def add_minimax_objective(am: AtaModel) -> cp_model.IntVar:
    """Add the minimax deviation objective; return the deviation var (scaled)."""
    m = am.model
    p = am.problem
    # Upper bound on any deviation: the largest target or total achievable info.
    max_info = sum(max(row) for row in am.scaled_info) or 1
    ub = max(max_info, max(am.scaled_target, default=0)) + 1
    y = m.new_int_var(0, ub, "minimax_dev")

    tol_scaled = round(p.tolerance * INFO_SCALE) if p.tolerance is not None else None
    for f in range(p.num_forms):
        for k in range(len(p.theta_points)):
            dev = am.form_info[f][k] - am.scaled_target[k]
            m.add(y >= dev)
            m.add(y >= -dev)
            if tol_scaled is not None:
                m.add(dev <= tol_scaled)
                m.add(-dev <= tol_scaled)
    m.minimize(y)
    return y


def add_maximin_objective(am: AtaModel) -> cp_model.IntVar:
    """Add the maximin information objective; return the floor var (scaled)."""
    m = am.model
    p = am.problem
    ub = (sum(max(row) for row in am.scaled_info) or 1) + 1
    t = m.new_int_var(0, ub, "maximin_info")
    for f in range(p.num_forms):
        for k in range(len(p.theta_points)):
            m.add(t <= am.form_info[f][k])
    m.maximize(t)
    return t
