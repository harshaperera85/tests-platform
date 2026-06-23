"""Redis + RQ wiring (assembly jobs run on the ``assembly`` queue).

Lazily constructed so import never dials Redis. RQ needs a raw (bytes) connection
— separate from the ``decode_responses`` client used for any cache reads.
"""

from __future__ import annotations

from functools import lru_cache

import redis
from rq import Queue

from app.core.config import settings

ASSEMBLY_QUEUE = "assembly"


@lru_cache
def get_redis() -> redis.Redis:
    """Text client (decode_responses) for cache-style reads."""
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@lru_cache
def get_rq_redis() -> redis.Redis:
    """Raw bytes client for RQ (job payloads are pickled)."""
    return redis.Redis.from_url(settings.redis_url)


@lru_cache
def get_queue() -> Queue:
    return Queue(ASSEMBLY_QUEUE, connection=get_rq_redis())
