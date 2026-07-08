"""Catalog of curriculum manifests (the §6 generator's course picker source).

Mirrors the simulated-pool pattern (`psychometrics/pools.py`): until a live
item-factory feed is wired, the platform ships curriculum data in-repo. The files
under ``app/data/curriculum/<slug>/unit-*.json`` are item-factory **unit JSON**
exports (slimmed to the consumed fields — complicator ``examples``/``misconceptions``
prose dropped); an optional ``<slug>/kc_configs/*.yml`` directory (slimmed
item-factory kc_configs) supplies §6.1 dimension counts where authored. Normalized
into manifests at first access and cached.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.generator import CurriculumManifest, CurriculumUnit
from app.services.blueprint_generator import normalize_unit_documents

_DATA_DIR = Path(__file__).parent.parent / "data" / "curriculum"


@lru_cache(maxsize=1)
def _catalog() -> dict[str, CurriculumManifest]:
    """course_id → manifest, one per curriculum directory."""
    out: dict[str, CurriculumManifest] = {}
    if not _DATA_DIR.is_dir():
        return out
    for course_dir in sorted(p for p in _DATA_DIR.iterdir() if p.is_dir()):
        docs = [
            CurriculumUnit.model_validate(json.loads(f.read_text()))
            for f in sorted(course_dir.glob("unit-*.json"))
        ]
        if not docs:
            continue
        # optional kc_configs/ alongside the unit JSONs supplies the §6.1
        # dimension counts (partial coverage; the rest is imputed)
        kc_dir = course_dir / "kc_configs"
        manifest = normalize_unit_documents(
            docs, kc_configs_dir=kc_dir if kc_dir.is_dir() else None
        )
        out[manifest.course_id] = manifest
    return out


def list_manifests() -> list[CurriculumManifest]:
    return list(_catalog().values())


def get_manifest(course_id: str) -> CurriculumManifest | None:
    return _catalog().get(course_id)
