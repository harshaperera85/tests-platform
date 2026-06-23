"""``assembly_job`` table — one assembly run against a blueprint (plan §8).

v1 runs assembly synchronously inside the request; the row still records strategy,
status, params and a result summary so the same shape works once long solves move
to RQ (plan §6/§7).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import JSONColumn, PkUuidMixin, TimestampMixin


class AssemblyJobRow(PkUuidMixin, TimestampMixin, Base):
    __tablename__ = "assembly_job"

    blueprint_id: Mapped[str] = mapped_column(
        ForeignKey("blueprint.id", ondelete="CASCADE"), index=True
    )
    #: owning test (nullable — standalone jobs have no test)
    test_id: Mapped[str | None] = mapped_column(
        ForeignKey("test.id", ondelete="CASCADE"), nullable=True, index=True
    )
    strategy: Mapped[str] = mapped_column(default="mip")
    #: which item pool the job assembled from (catalog id, plan §8 item_pool_ref)
    pool_id: Mapped[str] = mapped_column(
        default="small_2pl", server_default="small_2pl"
    )
    status: Mapped[str] = mapped_column(
        default="pending"
    )  # pending/optimal/feasible/infeasible/error
    params: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict)
    #: result summary: objective_value, method, theta_points, target_info, warnings
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)
