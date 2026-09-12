"""LLM / embedding provider implementations.

Cloud SDKs (langchain-openai, langchain-anthropic) are imported lazily inside
the methods so an Ollama-only install never needs them.
"""

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("ai.providers")


def _require(package: str, pip_name: str):
    try:
        return __import__(package)
    except ImportError as e:
        raise RuntimeError(
            f"This provider requires the optional '{pip_name}' package "
            f"(pip install {pip_name})."
        ) from e


class OllamaProvider:
    name = "ollama"

    def get_chat_model(self, api_key: str | None = None, **kwargs):
        from langchain_ollama import ChatOllama

        kwargs.pop("api_key", None)  # local Ollama needs no key; BYOK is a no-op
        kwargs.setdefault("temperature", 0.2)
        return ChatOllama(
            model=settings.LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            **kwargs,
        )

    def get_embedding_model(self):
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=settings.EMBEDDING_MODEL, base_url=settings.OLLAMA_BASE_URL)


class OpenAIProvider:
    name = "openai"

    @staticmethod
    def _kwargs():
        kw = {}
        if settings.OPENAI_BASE_URL:
            kw["base_url"] = settings.OPENAI_BASE_URL
        return kw

    def get_chat_model(self, api_key: str | None = None, **kwargs):
        # BYOK: an explicit api_key overrides the operator's managed key.
        key = api_key or settings.OPENAI_API_KEY
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set; export it to use the openai provider.")
        mod = _require("langchain_openai", "langchain-openai")
        kwargs.setdefault("temperature", 0.2)
        return mod.ChatOpenAI(model=settings.LLM_MODEL, api_key=key, **self._kwargs(), **kwargs)

    def get_embedding_model(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set; export it to use the openai provider.")
        mod = _require("langchain_openai", "langchain-openai")
        return mod.OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
            **self._kwargs(),
        )


class AnthropicProvider:
    name = "anthropic"

    def get_chat_model(self, api_key: str | None = None, **kwargs):
        key = api_key or settings.ANTHROPIC_API_KEY
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; export it to use the anthropic provider.")
        mod = _require("langchain_anthropic", "langchain-anthropic")
        kwargs.setdefault("temperature", 0.2)
        return mod.ChatAnthropic(model=settings.LLM_MODEL, api_key=key, **kwargs)

    def get_embedding_model(self):
        raise RuntimeError(
            "The anthropic provider has no embeddings endpoint; "
            "set EMBEDDING_PROVIDER=ollama or openai."
        )
