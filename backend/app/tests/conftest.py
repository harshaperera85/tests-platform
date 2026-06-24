"""Shared test fixtures.

API tests run against an in-memory SQLite database (the ORM uses a portable
``JSON``/``JSONB`` variant, so the same models work here and on Postgres). The
``get_db`` dependency is overridden to use a single shared connection.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.main import create_app
from app.models import Base
from app.psychometrics.bank import ItemPool, load_default_pool
from app.psychometrics.params import ItemParameters
from app.schemas.blueprint import Blueprint, ContentConstraint, TIFTarget


@pytest.fixture
def default_pool() -> ItemPool:
    return load_default_pool()


@pytest.fixture
def tiny_pool() -> ItemPool:
    """An 8-item pool small enough for the exhaustive reference oracle."""
    rows = [
        ("T0", 1.0, -1.5, "x"),
        ("T1", 1.2, -0.5, "x"),
        ("T2", 0.8, 0.0, "y"),
        ("T3", 1.5, 0.5, "y"),
        ("T4", 1.1, 1.0, "x"),
        ("T5", 0.9, -1.0, "y"),
        ("T6", 1.3, 0.2, "x"),
        ("T7", 1.0, -0.2, "y"),
    ]
    # canonical slope-intercept: d = -a*b
    return ItemPool(
        [
            ItemParameters(item_id=i, a=a, d=-a * b, tags={"KC": kc})
            for i, a, b, kc in rows
        ]
    )


@pytest.fixture
def tiny_blueprint() -> Blueprint:
    return Blueprint(
        name="tiny",
        length=4,
        statistical_target=TIFTarget(
            theta_points=[-0.5, 0.5], target_info=[1.0, 1.0], method="minimax"
        ),
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="x", minimum=2, maximum=3)
        ],
    )


@pytest.fixture
def linear_blueprint() -> Blueprint:
    """A realistic, satisfiable blueprint over the fixture pool."""
    return Blueprint(
        name="linear-demo",
        length=20,
        statistical_target=TIFTarget(
            # D=1 logistic magnitudes (small_2pl 20-item maximin ceiling ≈ 7.3/10/7.3)
            theta_points=[-1.0, 0.0, 1.0],
            target_info=[7.0, 9.0, 7.0],
            method="minimax",
        ),
        content_constraints=[
            ContentConstraint(tag_type="KC", tag_value="algebra", minimum=4, maximum=8),
            ContentConstraint(tag_type="KC", tag_value="geometry", minimum=4),
            ContentConstraint(tag_type="Bloom", tag_value="analyze", minimum=3),
        ],
    )


@pytest.fixture
def db_sessionmaker() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(db_sessionmaker: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app()

    def _override_get_db() -> Iterator[Session]:
        session = db_sessionmaker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
