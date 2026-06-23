"""Async assembly: the queued→execute lifecycle and the enqueue wiring.

Default config is synchronous (no Redis needed); these tests cover the async path:
``execute_job`` (the worker's solve, run directly with the test session) and
``dispatch`` enqueueing when ``assembly_async`` is on (with a fake queue).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.blueprint import BlueprintRow
from app.schemas.blueprint import Blueprint, ContentConstraint, TIFTarget
from app.services import assembly_run


def _blueprint() -> Blueprint:
    return Blueprint(
        name="async",
        length=12,
        statistical_target=TIFTarget(theta_points=[-1, 0, 1], target_info=[5, 7, 5]),
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="algebra", minimum=3)
        ],
    )


def test_execute_job_solves_queued_job(db_sessionmaker: sessionmaker) -> None:
    db = db_sessionmaker()
    try:
        bp = BlueprintRow(
            name="async",
            length=12,
            num_forms=1,
            spec=_blueprint().model_dump(mode="json"),
        )
        db.add(bp)
        db.commit()
        job = assembly_run.create_job(
            db,
            blueprint_row=bp,
            pool_id="small_2pl",
            strategy="mip",
            seed=0,
            time_limit_s=5,
        )
        assert job.status == "queued"

        done = assembly_run.execute_job(db, job)
        assert done.status in ("optimal", "feasible")
        assert done.result and done.result["method"] == "minimax"
        n_forms = db.query(BlueprintRow).count()  # sanity: row exists
        assert n_forms >= 1
        # re-running is idempotent (already terminal)
        again = assembly_run.execute_job(db, done)
        assert again.status == done.status
    finally:
        db.close()


def test_dispatch_async_enqueues(client: TestClient, monkeypatch) -> None:
    """With assembly_async on, the endpoint returns a queued job and enqueues."""
    enqueued: list[tuple] = []

    class _FakeQueue:
        def enqueue(self, fn, *args):  # noqa: ANN001
            enqueued.append((fn.__name__, args))

    monkeypatch.setattr(settings, "assembly_async", True)
    monkeypatch.setattr(assembly_run, "get_queue", lambda: _FakeQueue())

    tid = client.post(
        "/api/v1/tests", json={"name": "a", "pool_id": "small_2pl"}
    ).json()["id"]
    client.patch(
        f"/api/v1/tests/{tid}", json={"blueprint": _blueprint().model_dump(mode="json")}
    )
    job = client.post(f"/api/v1/tests/{tid}/assemble", json={"time_limit_s": 5})

    assert job.status_code == 201
    body = job.json()
    assert body["status"] == "queued"
    assert body["form_ids"] == []  # worker hasn't run yet
    assert enqueued and enqueued[0][0] == "execute_assembly_job"

    # the job is retrievable and still queued (no worker in this test)
    assert (
        client.get(f"/api/v1/assembly-jobs/{body['id']}").json()["status"] == "queued"
    )


@pytest.mark.usefixtures("client")
def test_sync_default_completes_inline(client: TestClient) -> None:
    """Default (assembly_async off) still completes in-request."""
    assert settings.assembly_async is False
    tid = client.post(
        "/api/v1/tests", json={"name": "s", "pool_id": "small_2pl"}
    ).json()["id"]
    client.patch(
        f"/api/v1/tests/{tid}", json={"blueprint": _blueprint().model_dump(mode="json")}
    )
    job = client.post(f"/api/v1/tests/{tid}/assemble", json={"time_limit_s": 5}).json()
    assert job["status"] in ("optimal", "feasible")
    assert len(job["form_ids"]) == 1
