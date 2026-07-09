"""Item-bank import schemas — the pinned item-factory export contract.

Shape per the issue-#1 resolution (`docs/item_factory_seam_investigation.md` §7):
the contract artifact is the SQLite-derived CAT-ready export. Items carry the R3
flat tag dict (``unit``/``kc`` values = the curriculum JSONs' UUIDs, verbatim), the
R4 identity fields (``instance_id`` adopted verbatim as ``item_id``; ``content_hash``
from the identity epoch onward), the editorial **status** lifecycle, structured
``enemy_of``, and **nullable IRT parameters** (a Stage-A/pre-calibration bank
legitimately has none — `docs/common_item_bank_design.md`).

Golden rule 4 applies at the document level: if ANY item carries parameters the
export MUST declare its metric ``{scaling_d, form, kind}`` (undeclared raises —
no silent default); cross-scale params are normalized to canonical D=1 at ingest.
"""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

#: Editorial statuses whose items may be administered (two-axis design: this is
#: axis A's contribution; axis B — calibration — is checked separately).
ADMINISTRABLE_EDITORIAL: frozenset[str] = frozenset({"live"})

#: Calibration statuses whose parameters may drive assembly (axis B).
ADMINISTRABLE_CALIBRATION: frozenset[str] = frozenset({"field_calibrated"})

CALIBRATION_STATUSES: frozenset[str] = frozenset(
    {"uncalibrated", "provisional", "field_calibrated", "recalibrating", "invalidated"}
)


class EnemyRef(BaseModel):
    """item-factory's structured enemy entry (R5); bare-string ids also accepted."""

    enemy_id: str
    reasons: list[str] | None = None
    type: str | None = None


class BankItemIn(BaseModel):
    """One exported item. ``instance_id`` is accepted as an alias of ``item_id``
    and carried verbatim — never re-minted (R4)."""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(validation_alias=AliasChoices("item_id", "instance_id"))
    template_id: str | None = None
    radical_config: Any | None = None
    #: identity-epoch integrity check; absent on pre-epoch exports
    content_hash: str | None = None
    #: editorial lifecycle (axis A), carried verbatim from item-factory
    status: str = "unknown"
    #: calibration lifecycle (axis B); derived when omitted (see service)
    calibration_status: str | None = None

    stem: str | None = None
    options: list[Any] | None = None
    answer_key: Any | None = None

    #: R3 flat tag dict: unit/kc/complicator (verbatim ids) + pinned cognitive dims
    tags: dict[str, str] = Field(default_factory=dict)
    enemy_of: list[EnemyRef | str] = Field(default_factory=list)

    # IRT parameters — nullable from birth (Stage A has none)
    a: float | None = None
    d: float | None = None
    c: float | None = None
    u: float | None = None
    se_a: float | None = None
    se_d: float | None = None
    cov_ad: float | None = None
    se_b: float | None = None

    #: calibration metadata (sample, date, model, …) — opaque here
    calibration: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check(self) -> BankItemIn:
        if self.calibration_status is not None and (
            self.calibration_status not in CALIBRATION_STATUSES
        ):
            raise ValueError(
                f"item {self.item_id}: unknown calibration_status "
                f"{self.calibration_status!r}; allowed: {sorted(CALIBRATION_STATUSES)}"
            )
        return self

    @property
    def has_params(self) -> bool:
        return self.a is not None or self.d is not None

    @property
    def enemy_ids(self) -> list[str]:
        return [e if isinstance(e, str) else e.enemy_id for e in self.enemy_of]


class ItemBankExportIn(BaseModel):
    """One item-bank export document, as POSTed to ``/item-bank/import``."""

    bank_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    export_version: str | int | None = None
    domain: str | None = None
    generated_at: str | None = None
    provenance: str | None = None
    #: REQUIRED (rule 4) when any item carries parameters
    metric: dict[str, Any] | None = None
    items: list[BankItemIn] = Field(min_length=1)


class BankIngestReport(BaseModel):
    bank_id: str
    n_items: int
    n_administrable: int
    #: two-axis breakdowns
    editorial_counts: dict[str, int]
    calibration_counts: dict[str, int]
    #: pool id registered in the catalog (only when n_administrable > 0)
    pool_id: str | None = None
    warnings: list[str]


class BankSummary(BaseModel):
    bank_id: str
    imported_at: str | None = None
    domain: str | None = None
    export_version: str | int | None = None
    n_items: int
    n_administrable: int
    editorial_counts: dict[str, int]
    calibration_counts: dict[str, int]
    pool_id: str | None = None
