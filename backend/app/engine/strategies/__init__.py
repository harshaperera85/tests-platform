"""Administration-model strategies.

One file per model (``linear.py``, later ``cat.py``, ``loft.py``, ``mst.py``). Each
implements ``AdministrationStrategy`` and self-registers via ``@register``. Importing
this package registers all built-in strategies, so the engine can resolve them by
``model_type``.
"""

from __future__ import annotations

from app.engine.strategies import (
    linear,  # noqa: F401  (registers LinearStrategy)
    loft,  # noqa: F401  (registers LoftStrategy)
)

__all__ = ["linear", "loft"]
