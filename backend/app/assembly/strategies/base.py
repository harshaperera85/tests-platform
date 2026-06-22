"""Pluggable assembly-strategy interface + registry.

The blueprint/model picks the rigor level on the assembly spectrum (plan §6):
``random_constrained`` (fast, low-stakes) ↔ ``mip`` (CP-SAT with TIF objective,
default for parallel forms) ↔ ``shadow`` (later). Strategies self-register and are
resolved by name, mirroring the administration-strategy registry pattern — adding a
strategy never edits this module or siblings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.assembly.blueprint_compiler import CompiledProblem
from app.assembly.result import AssemblyResult


class AssemblyStrategy(ABC):
    """One assembly algorithm. Takes a compiled problem, returns selected items."""

    #: stable identifier, e.g. "mip", "random_constrained"
    name: str

    @abstractmethod
    def assemble(
        self,
        problem: CompiledProblem,
        *,
        time_limit_s: float = 10.0,
        seed: int = 0,
    ) -> AssemblyResult: ...


_ASSEMBLY_REGISTRY: dict[str, type[AssemblyStrategy]] = {}


def register_strategy(cls: type[AssemblyStrategy]) -> type[AssemblyStrategy]:
    name = cls.name
    if not name:
        raise ValueError(f"{cls.__name__} must set a non-empty name")
    if name in _ASSEMBLY_REGISTRY:
        raise ValueError(f"assembly strategy {name!r} already registered")
    _ASSEMBLY_REGISTRY[name] = cls
    return cls


def get_assembly_strategy(name: str) -> AssemblyStrategy:
    try:
        return _ASSEMBLY_REGISTRY[name]()
    except KeyError as exc:
        raise KeyError(f"no assembly strategy registered for {name!r}") from exc


def available_strategies() -> list[str]:
    return sorted(_ASSEMBLY_REGISTRY)
