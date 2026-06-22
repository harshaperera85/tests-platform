"""The ``TestConfig`` discriminated union resolves the right branch by key."""

from __future__ import annotations

from pydantic import TypeAdapter

from app.schemas.test_config import CatConfig, LinearConfig, TestConfig

_adapter = TypeAdapter(TestConfig)


def test_linear_branch_resolves() -> None:
    cfg = _adapter.validate_python({"administration_model": "linear", "form_ref": "f1"})
    assert isinstance(cfg, LinearConfig)
    assert cfg.form_ref == "f1"


def test_cat_branch_resolves() -> None:
    cfg = _adapter.validate_python({"administration_model": "cat", "max_items": 30})
    assert isinstance(cfg, CatConfig)
    assert cfg.max_items == 30


def test_unknown_model_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _adapter.validate_python({"administration_model": "loft"})
