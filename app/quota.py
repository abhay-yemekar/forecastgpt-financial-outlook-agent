"""Hybrid key model (D-2): free daily quota for console users.

Console users (Supabase principals) get QUOTA_FREE_PER_DAY forecasts/day on
the operator's managed LLM key, plus a global daily cap (QUOTA_GLOBAL_PER_DAY)
that bounds total cost inside the provider's free tier. Supplying your own
provider key (BYOK) bypasses the per-user quota. API-key principals are
operator/dev-level and are rate-limited but not quota'd.

Counters are fixed UTC-day windows in Redis — the same primitive as the
rate limiter, no new infrastructure.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from redis import Redis

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("quota")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _seconds_until_midnight_utc() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def quota_usage(subject: str, redis_client: Redis | None = None) -> dict:
    """Current usage snapshot for one console user (no enforcement)."""
    client = redis_client or Redis.from_url(settings.REDIS_URL)
    day = _today()
    used = int(client.get(f"quota:user:{subject}:{day}") or 0)
    used_global = int(client.get(f"quota:global:{day}") or 0)
    return {
        "used": used,
        "limit": settings.QUOTA_FREE_PER_DAY,
        "global_used": used_global,
        "global_limit": settings.QUOTA_GLOBAL_PER_DAY,
        "resets_at": f"{day[:4]}-{day[4:6]}-{day[6:]}T00:00:00Z",
    }


def refund_user_quota(subject: str) -> None:
    """Give back one forecast slot (per-user + global counters) after a job
    FAILED. Failed forecasts must not consume the daily quota. Floor at 0."""
    client = Redis.from_url(settings.REDIS_URL)
    day = _today()
    for key in (f"quota:user:{subject}:{day}", f"quota:global:{day}"):
        try:
            value = int(client.get(key) or 0)
            if value > 0:
                client.decr(key)
        except Exception as e:  # refund is best-effort; never mask the job error
            log.warning(f"Quota refund failed for {subject}: {e}")


def enforce_user_quota(subject: str) -> None:
    """Count one forecast against the user's daily quota and the global cap.
    Raises 429 (with Retry-After seconds) when either is exhausted."""
    per_user = settings.QUOTA_FREE_PER_DAY
    global_cap = settings.QUOTA_GLOBAL_PER_DAY
    if per_user <= 0 and global_cap <= 0:
        return

    client = Redis.from_url(settings.REDIS_URL)
    day = _today()
    ttl = _seconds_until_midnight_utc()

    user_key = f"quota:user:{subject}:{day}"
    global_key = f"quota:global:{day}"
    # Increment both first; decrement back on rejection (no phantom usage).
    used = client.incr(user_key)
    client.expire(user_key, ttl + 60)
    used_global = client.incr(global_key)
    client.expire(global_key, ttl + 60)

    over_user = per_user > 0 and used > per_user
    over_global = global_cap > 0 and used_global > global_cap
    if over_user or over_global:
        client.decr(user_key)
        client.decr(global_key)
        which = (
            "Your daily free quota is used up"
            if over_user
            else "The service-wide free quota is used up for today"
        )
        retry_after = _seconds_until_midnight_utc()
        log.warning(f"Quota exhausted for user {subject}: used={used}/{per_user} global={used_global}/{global_cap}")
        raise HTTPException(
            status_code=429,
            detail=f"{which}. Bring your own provider key (X-Provider-Key header) "
            "for unlimited use, or try again tomorrow.",
            headers={"Retry-After": str(retry_after)},
        )
