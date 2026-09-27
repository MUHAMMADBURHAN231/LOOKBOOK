from functools import lru_cache

import redis
import redis.asyncio as aioredis

from app.core.config import get_settings


@lru_cache
def async_redis() -> aioredis.Redis:
    return aioredis.from_url(get_settings().redis_url, decode_responses=True)


@lru_cache
def sync_redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def task_channel(task_id: str) -> str:
    return f"channel:tasks:{task_id}"
