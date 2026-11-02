import pytest

from app.ai import selftest
from app.config import settings


class _Chat:
    def __init__(self, error=None):
        self.error = error

    def invoke(self, messages):
        if self.error:
            raise self.error
        return type("Msg", (), {"content": "OK"})()


class _Emb:
    def __init__(self, error=None):
        self.error = error

    def embed_query(self, text):
        if self.error:
            raise self.error
        return [0.1, 0.2]


def _providers(monkeypatch, chat_error=None, emb_error=None):
    chat = type("P", (), {"get_chat_model": lambda self, **kw: _Chat(chat_error)})
    emb = type("P", (), {"get_embedding_model": lambda self: _Emb(emb_error)})
    monkeypatch.setattr(selftest, "get_llm_provider", lambda: chat())
    monkeypatch.setattr(selftest, "get_embedding_provider", lambda: emb())
    monkeypatch.setattr(selftest, "status", {"chat": "unchecked", "embeddings": "unchecked"})


def test_self_test_reports_ok(monkeypatch):
    _providers(monkeypatch)
    assert selftest.run_model_self_test() == {"chat": "ok", "embeddings": "ok"}


def test_self_test_reports_failures_by_class_only(monkeypatch, caplog):
    class NotFoundError(Exception):
        pass

    _providers(
        monkeypatch,
        chat_error=NotFoundError("models/gemini-2.0-flash-lite is no longer available; key sk-secret"),
        emb_error=RuntimeError("501 UNIMPLEMENTED"),
    )
    result = selftest.run_model_self_test()
    assert result == {"chat": "failed (NotFoundError)", "embeddings": "failed (RuntimeError)"}
    # The public status never carries provider error text; the log does.
    assert "sk-secret" not in str(result)
    assert "MODEL SELF-TEST FAILED" in caplog.text
    assert "gemini-2.0-flash-lite is no longer available" in caplog.text


def test_self_test_disabled_starts_nothing(monkeypatch):
    monkeypatch.setattr(settings, "MODEL_SELF_TEST", False)

    def boom(*a, **k):
        raise AssertionError("self-test thread started while disabled")

    monkeypatch.setattr(selftest.threading, "Thread", boom)
    selftest.start_model_self_test()


@pytest.mark.parametrize(
    ("base_url", "expect_ctx_check"),
    [("https://generativelanguage.googleapis.com/v1beta/openai/", False), ("", None)],
)
def test_openai_compatible_embeddings_send_plain_strings(monkeypatch, base_url, expect_ctx_check):
    """Gemini's OpenAI-compatible endpoint rejects token-ID arrays (501), so
    a custom base URL must turn LangChain's pre-tokenizing off."""
    from app.ai.providers import OpenAIProvider

    captured = {}

    class FakeEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_mod = type("Mod", (), {"OpenAIEmbeddings": FakeEmbeddings})
    monkeypatch.setattr("app.ai.providers._require", lambda package, pip_name: fake_mod)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "k")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", base_url)
    OpenAIProvider().get_embedding_model()
    assert captured.get("check_embedding_ctx_length") == expect_ctx_check
