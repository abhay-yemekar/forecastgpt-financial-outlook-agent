"""API-key authentication for the developer-facing endpoints.

Keys look like `fgpt_<32 random url-safe chars>`; only a SHA-256 hash is
stored, so a leaked database does not leak working keys. Passwords are
hashed with Argon2id.
"""

import hashlib
import secrets
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.models import ApiKey
from app.db.mysql import get_db
from app.utils.logger import get_logger

log = get_logger("auth")

_ph = PasswordHasher()  # Argon2id with library defaults

KEY_SCHEME = "fgpt"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_hash, prefix). The raw key is shown exactly once
    at creation; only the hash and prefix are persisted."""
    raw = f"{KEY_SCHEME}_{secrets.token_urlsafe(32)}"
    return raw, hash_key(raw), raw[:12]


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    """FastAPI dependency: a valid, non-revoked X-API-Key header."""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Pass the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    row = db.query(ApiKey).filter(ApiKey.key_hash == hash_key(x_api_key)).first()
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
    row.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return row
