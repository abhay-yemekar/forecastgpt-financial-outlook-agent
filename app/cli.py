"""User / API-key management CLI.

Usage:
  python -m app.cli user create --email you@example.com --password secret
  python -m app.cli key create --email you@example.com --password secret
  python -m app.cli key list --email you@example.com
  python -m app.cli key revoke --prefix fgpt_AbC123

The raw key is printed exactly once at creation; only its SHA-256 hash is
stored. Issuing a key requires the account password to prove ownership.
"""

import argparse
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import FlushError

from app.auth import generate_api_key, hash_password, verify_password
from app.db.models import ApiKey, User
from app.db.mysql import SessionLocal


def create_user(email: str, password: str) -> User:
    db = SessionLocal()
    try:
        user = User(email=email, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        return user
    finally:
        db.close()


def create_key(email: str, password: str) -> tuple[str, ApiKey]:
    """Verify the password, then mint a key. Returns (raw_key, row)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None or not verify_password(user.password_hash, password):
            raise SystemExit("Wrong email or password.")
        raw, key_hash, prefix = generate_api_key()
        row = ApiKey(user_id=user.id, key_hash=key_hash, prefix=prefix)
        db.add(row)
        db.commit()
        return raw, row
    finally:
        db.close()


def list_keys(email: str) -> list[dict]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise SystemExit(f"No user with email {email}.")
        rows = db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.id).all()
        return [
            {
                "prefix": r.prefix,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "revoked": r.revoked_at is not None,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            }
            for r in rows
        ]
    finally:
        db.close()


def revoke_key(prefix: str) -> ApiKey | None:
    db = SessionLocal()
    try:
        row = db.query(ApiKey).filter(ApiKey.prefix == prefix).first()
        if row is None:
            raise SystemExit(f"No API key with prefix '{prefix}'.")
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return row
    finally:
        db.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="app.cli", description="ForecastGPT user/API-key management")
    sub = parser.add_subparsers(dest="command", required=True)

    p_user = sub.add_parser("user")
    user_sub = p_user.add_subparsers(dest="user_command", required=True)
    p_user_create = user_sub.add_parser("create")
    p_user_create.add_argument("--email", required=True)
    p_user_create.add_argument("--password", required=True)

    p_key = sub.add_parser("key")
    key_sub = p_key.add_subparsers(dest="key_command", required=True)
    p_key_create = key_sub.add_parser("create")
    p_key_create.add_argument("--email", required=True)
    p_key_create.add_argument("--password", required=True)
    p_key_list = key_sub.add_parser("list")
    p_key_list.add_argument("--email", required=True)
    p_key_revoke = key_sub.add_parser("revoke")
    p_key_revoke.add_argument("--prefix", required=True)

    args = parser.parse_args(argv)

    if args.command == "user" and args.user_command == "create":
        try:
            user = create_user(args.email, args.password)
            print(f"Created user {user.email} (id={user.id}).")
        except (IntegrityError, FlushError) as e:
            raise SystemExit(f"User {args.email} already exists.") from e
    elif args.command == "key" and args.key_command == "create":
        raw, row = create_key(args.email, args.password)
        print(f"API key created (id={row.id}, prefix={row.prefix}).")
        print("Store it now — it cannot be shown again:")
        print(raw)
    elif args.command == "key" and args.key_command == "list":
        for k in list_keys(args.email):
            revoked = " [REVOKED]" if k["revoked"] else ""
            print(f"{k['prefix']}  created={k['created_at']}  last_used={k['last_used_at']}{revoked}")
    elif args.command == "key" and args.key_command == "revoke":
        revoke_key(args.prefix)
        print(f"Revoked key with prefix {args.prefix}.")


if __name__ == "__main__":
    main()
