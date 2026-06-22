"""Assembly strategies. Importing the package registers all built-in strategies.

Concrete strategies self-register via ``@register_strategy`` at import time, so a
single ``import app.assembly.strategies`` makes ``mip`` and ``random_constrained``
resolvable through :func:`get_assembly_strategy`.
"""

from __future__ import annotations

from app.assembly.strategies import mip, random_constrained  # noqa: F401  (register)
from app.assembly.strategies.base import (
    AssemblyStrategy,
    available_strategies,
    get_assembly_strategy,
    register_strategy,
)

__all__ = [
    "AssemblyStrategy",
    "available_strategies",
    "get_assembly_strategy",
    "register_strategy",
]
