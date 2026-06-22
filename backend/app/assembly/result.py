"""Assembly result types — the output contract every strategy returns.

Strategy-agnostic so ``mip`` and ``random_constrained`` (and later ``shadow``) are
swappable behind one shape (plan §6). The actual-vs-target TIF carried here is what
the form-preview endpoint plots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AssemblyStatus = Literal["optimal", "feasible", "infeasible", "error"]


@dataclass(frozen=True)
class FormSolution:
    """One assembled form: ordered item ids + its realized TIF at the theta points."""

    item_ids: list[str]
    tif_actual: list[float]


@dataclass
class AssemblyResult:
    """The outcome of an assembly job (one or more parallel forms)."""

    strategy: str
    status: AssemblyStatus
    theta_points: list[float]
    target_info: list[float]
    method: str
    forms: list[FormSolution] = field(default_factory=list)
    #: minimax: worst-point absolute |actual-target|; maximin: worst-point info.
    objective_value: float | None = None
    solve_time_s: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return self.status in ("optimal", "feasible")
