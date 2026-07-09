"""Item-bank import endpoints (backlog #9) — the real item-data swap point.

``POST /item-bank/import`` ingests an item-factory CAT-ready export (the pinned
contract). The full two-axis bank is persisted as the record; an administrable
pool is derived into the standard catalog when the bank carries live, calibrated
items — after which every existing pool consumer (editor, assembly, QA) uses it
with no further wiring.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.item_bank import BankIngestReport, BankSummary, ItemBankExportIn
from app.services.item_bank import BankIngestError, ingest_export, list_banks

router = APIRouter(prefix="/item-bank", tags=["item-bank"])


@router.post("/import", response_model=BankIngestReport)
def import_item_bank(doc: ItemBankExportIn) -> BankIngestReport:
    """Validate + ingest one export document. Fatal problems (duplicate ids,
    partial parameters, undeclared metric with parameters present, reserved
    bank id) return 422 with nothing persisted; data-quality findings come back
    as warnings on the report. Re-importing a bank_id replaces it (content-hash
    changes under unchanged ids are reported — identity-contract violations)."""
    try:
        return ingest_export(doc)
    except BankIngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[BankSummary])
def get_item_banks() -> list[BankSummary]:
    """All imported banks with their two-axis status breakdowns."""
    return list_banks()
