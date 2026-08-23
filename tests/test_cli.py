import pytest

from app import cli
from app.db.models import ApiKey, User
from app.db.mysql import SessionLocal


def _unique_email():

    _unique_email.n = getattr(_unique_email, "n", 0) + 1
    return f"user{_unique_email.n}@example.com"


def test_user_create_and_duplicate_rejected(capsys):
    email = _unique_email()
    cli.main(["user", "create", "--email", email, "--password", "pw123456"])
    assert "Created user" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["user", "create", "--email", email, "--password", "pw123456"])


def test_key_create_requires_correct_password():
    email = _unique_email()
    cli.main(["user", "create", "--email", email, "--password", "pw123456"])
    with pytest.raises(SystemExit, match="Wrong email or password"):
        cli.main(["key", "create", "--email", email, "--password", "nope"])


def test_key_lifecycle_create_list_revoke(capsys):
    email = _unique_email()
    cli.main(["user", "create", "--email", email, "--password", "pw123456"])

    cli.main(["key", "create", "--email", email, "--password", "pw123456"])
    out = capsys.readouterr().out
    assert "cannot be shown again" in out
    raw_key = out.strip().splitlines()[-1]
    assert raw_key.startswith("fgpt_")

    cli.main(["key", "list", "--email", email])
    listed = capsys.readouterr().out
    assert raw_key[:12] in listed

    cli.main(["key", "revoke", "--prefix", raw_key[:12]])
    db = SessionLocal()
    try:
        row = db.query(ApiKey).filter(ApiKey.prefix == raw_key[:12]).first()
        assert row.revoked_at is not None
        assert db.query(User).filter(User.email == email).count() == 1
    finally:
        db.close()
