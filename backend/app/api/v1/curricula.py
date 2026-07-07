"""Curriculum catalog endpoints — the course picker behind the §6 generator UI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.generator import CurriculumManifest, CurriculumSummary
from app.services import curricula

router = APIRouter(prefix="/curricula", tags=["curricula"])


@router.get("", response_model=list[CurriculumSummary])
def list_curricula() -> list[CurriculumSummary]:
    """All curricula available to generate blueprints from."""
    return [
        CurriculumSummary(
            course_id=m.course_id,
            course_name=m.course_name,
            n_units=len(m.units),
            n_kcs=sum(len(u.kcs) for u in m.units),
            units=m.units,
        )
        for m in curricula.list_manifests()
    ]


@router.get("/{course_id}", response_model=CurriculumManifest)
def get_curriculum(course_id: str) -> CurriculumManifest:
    manifest = curricula.get_manifest(course_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"unknown course_id {course_id!r}")
    return manifest
