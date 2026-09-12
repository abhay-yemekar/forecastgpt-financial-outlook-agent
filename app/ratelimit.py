"""Per-API-key rate limiting: fixed-window counters in Redis.

Two independent buckets: "post" (forecast submissions, expensive —
RATE_LIMIT_PER_MINUTE) and "get" (status reads, cheap —
RATE_LIMIT_GET_PER_MINUTE, sized so a client polling every few seconds
never starves its own submission budget).
"""

import time

from fastapi import HTTPException
from redis import Redis

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("ratelimit")

WINDOW_SECONDS = 60


def enforce_rate_limit(subject: str | int, bucket: str = "post") -> None:
    """Raise HTTP 429 once this subject (api-key:<id> or user:<sub>) exceeds
    its bucket limit in the current window. Set the matching env to 0 to
    disable a bucket (e.g. in tests)."""
    limit = (
        settings.RATE_LIMIT_PER_MINUTE
        if bucket == "post"
        else settings.RATE_LIMIT_GET_PER_MINUTE
    )
    if limit <= 0:
        return

    client = Redis.from_url(settings.REDIS_URL)
    window = int(time.time()) // WINDOW_SECONDS
    redis_key = f"ratelimit:{bucket}:{subject}:{window}"
    count = client.incr(redis_key)
    if count == 1:
        client.expire(redis_key, WINDOW_SECONDS + 1)

    if count > limit:
        retry_after = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        log.warning(f"Rate limit hit for subject {subject} bucket={bucket} ({count}/{limit}).")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {limit} requests per minute per API key.",
            headers={"Retry-After": str(retry_after)},
        )
