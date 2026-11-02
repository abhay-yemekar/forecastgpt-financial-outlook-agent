import pytest

from app.db.mysql import check_database_url

POOLER = "aws-0-ap-south-1.pooler.supabase.com:6543/postgres"


@pytest.mark.parametrize(
    "url",
    [
        f"postgresql+psycopg2://postgres.ref:plainpass123@{POOLER}",
        f"postgresql+psycopg2://postgres.ref:p%40ss%23word@{POOLER}",
        "sqlite:///./forecastgpt_fallback.db",
    ],
)
def test_valid_urls_pass(url):
    check_database_url(url)


def test_raw_at_in_password_is_rejected_without_echoing_it():
    with pytest.raises(RuntimeError) as exc:
        check_database_url(f"postgresql+psycopg2://postgres.ref:secret@tail99@{POOLER}")
    assert "%40" in str(exc.value)
    assert "secret" not in str(exc.value) and "tail99" not in str(exc.value)


@pytest.mark.parametrize(
    "url",
    [
        "not a url secret99",
        # The separator '@' encoded too: the password is read as a port.
        f"postgresql+psycopg2://postgres.ref:secret99%40{POOLER}",
    ],
)
def test_unparsable_url_is_rejected_without_echoing_it(url):
    with pytest.raises(RuntimeError) as exc:
        check_database_url(url)
    assert "secret99" not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__
