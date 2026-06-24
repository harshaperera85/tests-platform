"""Optional metric *reporting* transforms (presentation / interop only).

The canonical internal metric is **logistic D = 1** (:data:`CANONICAL_D` in
:mod:`app.psychometrics.params`); all stored parameters and all computation
(probability, Fisher information, theta) live there. These helpers re-express
canonical quantities in a *different* scaling convention — most usefully the
**normal-ogive D = 1.702** convention some psychometric reporting prefers — for
DISPLAY or for handing parameters to an external tool that expects that metric.

They are pure functions of already-computed canonical values and **never** mutate
stored params or the internal computation. The default display convention is
native (``D = 1``); flip it via the single config setting ``display_metric_d``.

What changes under a relabel to display constant ``D_disp`` (preserving the
response function, i.e. ``D_disp * a_disp = CANONICAL_D * a_canonical``):

- **discrimination** ``a`` scales by ``CANONICAL_D / D_disp`` (e.g. /1.702 for
  normal-ogive). This is the only quantity whose *number* changes.
- **theta** and **difficulty** ``b`` are locations on the ability scale and are
  **invariant** (a relabel does not move them).
- **information** about theta is a property of the (unchanged) response function
  and is therefore **invariant** too: ``D_disp^2 * a_disp^2 = CANONICAL_D^2 *
  a_canonical^2``. So "information in normal-ogive terms" is the same number.
"""

from __future__ import annotations

from app.psychometrics.params import CANONICAL_D

#: The normal-ogive scaling constant, the usual non-native reporting convention.
NORMAL_OGIVE_D: float = 1.702


def report_discrimination(
    a_canonical: float, display_d: float = NORMAL_OGIVE_D
) -> float:
    """Express a canonical (D=1) discrimination in ``display_d`` terms.

    Preserves the response function: ``display_d * a_disp == CANONICAL_D * a``.
    """
    return a_canonical * (CANONICAL_D / display_d)


def report_difficulty(b_canonical: float, display_d: float = NORMAL_OGIVE_D) -> float:
    """Difficulty/location is invariant under a metric relabel (identity)."""
    return b_canonical


def report_theta(theta_canonical: float, display_d: float = NORMAL_OGIVE_D) -> float:
    """Theta is a location on the ability scale; invariant under relabel (identity)."""
    return theta_canonical


def report_information(
    info_canonical: float, display_d: float = NORMAL_OGIVE_D
) -> float:
    """Fisher information about theta is invariant under a metric relabel (identity).

    Provided for API symmetry / explicitness; intentionally returns the value
    unchanged (see module docstring for why).
    """
    return info_canonical
