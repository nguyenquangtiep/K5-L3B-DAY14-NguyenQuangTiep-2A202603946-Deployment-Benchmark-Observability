"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""
import hashlib
import uuid

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r


WINDOW_SECONDS = 60

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local member = ARGV[3]

local server_time = redis.call('TIME')
local now = tonumber(server_time[1]) * 1000
    + math.floor(tonumber(server_time[2]) / 1000)

redis.call(
    'ZREMRANGEBYSCORE',
    key, '-inf', now - window
)

local count = redis.call('ZCARD', key)

if count >= limit then
    local oldest = redis.call(
        'ZRANGE', key, 0, 0, 'WITHSCORES'
    )

    local retry = math.ceil(
        (tonumber(oldest[2]) + window - now) / 1000
    )

    return {0, math.max(1, retry)}
end

redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)

return {1, 0}
"""

def check_rate_limit(key: str) -> None:
    key_hash = hashlib.sha256(
        key.encode()
    ).hexdigest()

    redis_key = f"rate_limit:{key_hash}"

    try:
        allowed, retry_after = r.eval(
            RATE_LIMIT_SCRIPT,
            1,
            redis_key,
            settings.rate_limit_per_minute,
            WINDOW_SECONDS * 1000,
            uuid.uuid4().hex,
        )

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Rate limiter unavailable",
        )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(retry_after),
            },
        )
