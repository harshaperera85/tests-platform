"""RQ tasks. The worker process runs these; they open their own DB session.

Enqueued by the API (``services.assembly_run.dispatch``) when assembly is async.
"""

from __future__ import annotations

from app.core.db import get_sessionmaker
from app.models.assembly_job import AssemblyJobRow
from app.services.assembly_run import execute_job


def execute_assembly_job(job_id: str) -> str:
    """Solve a queued assembly job by id and persist its forms + status."""
    session = get_sessionmaker()()
    try:
        job = session.get(AssemblyJobRow, job_id)
        if job is None:
            return "missing"
        execute_job(session, job)
        return job.status
    finally:
        session.close()
