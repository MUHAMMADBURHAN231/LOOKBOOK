"""Redis token-bucket rate limiter.

The bucket update runs as a single Lua script, so concurrent requests can't race each other
past the limit (a read-then-write pipeline would let bursts through under load).
"""

import math

from fastapi import HTTPException, status

from app.core.redis import async_redis

_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local state = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(state[1]) or capacity
local ts = tonumber(state[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - ts) * rate)

local allowed = 0
local retry_after = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_after = (cost - tokens) / rate
end
redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) + 60)
return {allowed, tostring(retry_after)}
"""


async def check_rate_limit(bucket: str, limit: int, per_seconds: int, detail: str | None = None) -> None:
    """Allow `limit` requests per `per_seconds` (with bursts up to `limit`); raise 429 otherwise."""
    r = async_redis()
    now = (await r.time())
    now_s = now[0] + now[1] / 1_000_000
    allowed, retry_after = await r.eval(
        _LUA, 1, f"rate_limit:{bucket}", limit / per_seconds, limit, now_s, 1
    )
    if int(allowed) != 1:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail or "Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(max(1, math.ceil(float(retry_after))))},
        )
