import pytest

from app.ai import factory
from app.ai.providers import AnthropicProvider, OllamaProvider, OpenAIProvider
from app.config import settings


def test_default_provider_is_ollama(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    assert isinstance(factory.get_llm_provider(), OllamaProvider)


def test_provider_names_map_to_classes(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    assert isinstance(factory.get_llm_provider(), OpenAIProvider)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    assert isinstance(factory.get_llm_provider(), AnthropicProvider)


def test_provider_name_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", " Ollama ")
    assert isinstance(factory.get_llm_provider(), OllamaProvider)


def test_unknown_provider_raises_with_options(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")
    with pytest.raises(ValueError, match="ollama"):
        factory.get_llm_provider()


def test_unknown_embedding_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "anthropic")
    with pytest.raises(ValueError):
        factory.get_embedding_provider()


def test_ollama_chat_model_uses_configured_model():
    llm = factory.get_llm_provider().get_chat_model(temperature=0.2)
    assert llm.model == settings.LLM_MODEL or getattr(llm, "model_name", None) == settings.LLM_MODEL


def test_openai_without_key_fails_fast(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        factory.get_llm_provider().get_chat_model()


def test_anthropic_embeddings_not_supported(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "ollama")  # chat stays valid
    provider = AnthropicProvider()
    with pytest.raises(RuntimeError, match="no embeddings endpoint"):
        provider.get_embedding_model()
