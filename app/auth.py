"""API-key authentication for the developer-facing endpoints.

Keys look like `fgpt_<32 random url-safe chars>`; only a SHA-256 hash is
stored, so a leaked database does not leak working keys. Passwords are
hashed with Argon2id.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
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


# ---------------------------------------------------------------------------
# Principals: API keys (developers/operator) OR Supabase JWTs (console users)
# ---------------------------------------------------------------------------


@dataclass
class Principal:
    kind: str  # "api_key" | "user"
    id: str  # api key row id, or the Supabase JWT `sub`
    label: str  # display hint (key prefix / email)

    @property
    def is_user(self) -> bool:
        return self.kind == "user"

    @property
    def rate_limit_key(self) -> str:
        return f"api-key:{self.id}" if self.kind == "api_key" else f"user:{self.id}"


def decode_supabase_jwt(token: str) -> dict:
    """Verify a Supabase access token (HS256, signed with the project's JWT
    secret). Raises HTTPException with a clear status on any problem."""
    if not settings.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Console login is not configured on this deployment "
            "(SUPABASE_JWT_SECRET is unset). Use an API key instead.",
        )
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired; sign in again.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.") from None


def get_current_principal(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """Accept either an X-API-Key (developer/operator path) or a Supabase
    Bearer JWT (console-user path). Exactly one is required."""
    if authorization and authorization.lower().startswith("bearer "):
        claims = decode_supabase_jwt(authorization[7:].strip())
        return Principal(
            kind="user",
            id=str(claims["sub"]),
            label=claims.get("email") or claims["sub"],
        )

    if x_api_key:
        row = db.query(ApiKey).filter(ApiKey.key_hash == hash_key(x_api_key)).first()
        if row is None or row.revoked_at is not None:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
        row.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return Principal(kind="api_key", id=str(row.id), label=f"…{row.prefix[-6:]}")

    raise HTTPException(
        status_code=401,
        detail="Sign in (Authorization: Bearer <session>) or pass X-API-Key.",
        headers={"WWW-Authenticate": "ApiKey, Bearer"},
    )
