"""Strategy registry.

Strategies self-register by decorating their class with ``@register``. The engine
core resolves a strategy by ``model_type`` via ``get_strategy``. Registering a new
model touches only the new strategy file — never this module or siblings.
"""

from __future__ import annotations

from app.engine.contract import AdministrationStrategy

_REGISTRY: dict[str, type[AdministrationStrategy]] = {}


def register(
    strategy_cls: type[AdministrationStrategy],
) -> type[AdministrationStrategy]:
    """Class decorator: register a strategy under its ``model_type``."""
    model_type = strategy_cls.model_type
    if not model_type:
        raise ValueError(f"{strategy_cls.__name__} must set a non-empty model_type")
    if model_type in _REGISTRY:
        raise ValueError(f"model_type {model_type!r} already registered")
    _REGISTRY[model_type] = strategy_cls
    return strategy_cls


def get_strategy(model_type: str) -> AdministrationStrategy:
    """Instantiate the strategy registered for ``model_type``."""
    try:
        return _REGISTRY[model_type]()
    except KeyError as exc:
        raise KeyError(f"no strategy registered for model_type {model_type!r}") from exc


def is_registered(model_type: str) -> bool:
    return model_type in _REGISTRY


def registered_models() -> list[str]:
    return sorted(_REGISTRY)
