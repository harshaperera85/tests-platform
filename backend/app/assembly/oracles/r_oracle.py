"""Bridge to the R assembly oracles (DEV/TEST ONLY).

Runs the same compiled problem through ``TestDesign::Static`` or ``eatATA`` inside
the R toolchain and returns its selection + objective for parity checking against
the owned engine. The R packages are GPL and are **never** a runtime dependency
(CLAUDE.md golden rule 2) — this module shells out to ``Rscript`` only from tests.

When ``Rscript`` or the requested package is missing (e.g. on the host, where R
lives only in the ``scoring-r`` container), :func:`is_available` returns ``False``
and the parity test skips. To exercise it, run inside an image that has R +
``eatATA``/``TestDesign`` + ``jsonlite`` installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.assembly.blueprint_compiler import CompiledProblem

_R_SCRIPT = Path(__file__).parent / "ata_oracle.R"
_RUN_TIMEOUT_S = 120


@dataclass(frozen=True)
class ROracleResult:
    status: str
    objective_value: float | None
    item_ids: list[str] | None
    package: str
    solver: str | None = None
    solve_time_s: float | None = None


@lru_cache(maxsize=4)
def is_available(package: str = "eatATA") -> bool:
    """True iff ``Rscript`` and the requested R package are importable."""
    rscript = shutil.which("Rscript")
    if rscript is None:
        return False
    try:
        proc = subprocess.run(
            [
                rscript,
                "-e",
                f'quit(status = !requireNamespace("{package}", quietly=TRUE))',
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _serialize(problem: CompiledProblem) -> dict[str, object]:
    return {
        "item_ids": list(problem.item_ids),
        "info": [list(row) for row in problem.info],
        # native canonical slope-intercept params (a, d, g, u) — D=1 logistic, the
        # mirt-native metric; the harness can recompute info or hand these to mirt.
        "params": [
            {"a": a, "d": d, "g": g, "u": u} for (a, d, g, u) in problem.params
        ],
        "metric": {"scaling_d": 1.0, "form": "slope_intercept"},
        "theta_points": list(problem.theta_points),
        "target_info": list(problem.target_info),
        "method": problem.method,
        "length": problem.length,
        "content_sets": [
            {
                "key": cs.key,
                "members": [m + 1 for m in cs.members],  # R is 1-based
                "minimum": cs.minimum,
                "maximum": cs.maximum,
            }
            for cs in problem.content_sets
        ],
        "enemy_pairs": [[i + 1, j + 1] for i, j in problem.enemy_pairs],
    }


def run_oracle(problem: CompiledProblem, *, package: str = "eatATA") -> ROracleResult:
    """Assemble ``problem`` via the R oracle. Raises if R is unavailable."""
    if problem.num_forms != 1:
        raise ValueError("R oracle bridge supports single-form problems only")
    if not is_available(package):
        raise RuntimeError(f"R oracle unavailable (Rscript / {package} missing)")

    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "problem.json"
        in_path.write_text(json.dumps(_serialize(problem)))
        proc = subprocess.run(
            ["Rscript", str(_R_SCRIPT), str(in_path), package],
            capture_output=True,
            text=True,
            timeout=_RUN_TIMEOUT_S,
            check=True,
        )
    payload = json.loads(proc.stdout)
    return ROracleResult(
        status=payload["status"],
        objective_value=payload.get("objective"),
        item_ids=payload.get("item_ids"),
        package=package,
        solver=payload.get("solver"),
    )


def run_oracle_http(
    problem: CompiledProblem,
    *,
    base_url: str,
    package: str = "eatATA",
    timeout: float = 60.0,
) -> ROracleResult:
    """Solve ``problem`` via the runtime oracle-r HTTP service (read-only).

    Used by the cross-validation endpoint. The service consumes the same serialized
    CompiledProblem (canonical D=1 info matrix + constraints) as the CLI bridge.
    """
    if problem.num_forms != 1:
        raise ValueError("oracle cross-validation supports single-form problems only")
    body = dict(_serialize(problem))
    body["package"] = package
    req = urllib.request.Request(
        base_url.rstrip("/") + "/assemble",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted)
        payload = json.loads(resp.read())
    if payload.get("status") == "error":
        return ROracleResult(
            status="error",
            objective_value=None,
            item_ids=None,
            package=package,
            solve_time_s=payload.get("solve_time_s"),
        )
    return ROracleResult(
        status=payload["status"],
        objective_value=payload.get("objective"),
        item_ids=payload.get("item_ids"),
        package=package,
        solver=payload.get("solver"),
        solve_time_s=payload.get("solve_time_s"),
    )
