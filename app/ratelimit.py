"""Per-API-key rate limiting: a fixed-window counter in Redis."""

import time

from fastapi import HTTPException
from redis import Redis

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("ratelimit")

WINDOW_SECONDS = 60


def enforce_rate_limit(api_key_id: int) -> None:
    """Raise HTTP 429 once this key exceeds RATE_LIMIT_PER_MINUTE in the
    current window. Fixed-window is deliberately simple; set the env to 0
    to disable limiting (e.g. in tests)."""
    limit = settings.RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return

    client = Redis.from_url(settings.REDIS_URL)
    window = int(time.time()) // WINDOW_SECONDS
    bucket = f"ratelimit:{api_key_id}:{window}"
    count = client.incr(bucket)
    if count == 1:
        client.expire(bucket, WINDOW_SECONDS + 1)

    if count > limit:
        retry_after = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        log.warning(f"Rate limit hit for api_key id={api_key_id} ({count}/{limit} in window).")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {limit} requests per minute per API key.",
            headers={"Retry-After": str(retry_after)},
        )
