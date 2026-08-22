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

    def get_chat_model(self, **kwargs):
        from langchain_ollama import ChatOllama

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

    def get_chat_model(self, **kwargs):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set; export it to use the openai provider.")
        mod = _require("langchain_openai", "langchain-openai")
        kwargs.setdefault("temperature", 0.2)
        return mod.ChatOpenAI(model=settings.LLM_MODEL, api_key=settings.OPENAI_API_KEY, **kwargs)

    def get_embedding_model(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set; export it to use the openai provider.")
        mod = _require("langchain_openai", "langchain-openai")
        return mod.OpenAIEmbeddings(model=settings.EMBEDDING_MODEL, api_key=settings.OPENAI_API_KEY)


class AnthropicProvider:
    name = "anthropic"

    def get_chat_model(self, **kwargs):
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; export it to use the anthropic provider.")
        mod = _require("langchain_anthropic", "langchain-anthropic")
        kwargs.setdefault("temperature", 0.2)
        return mod.ChatAnthropic(model=settings.LLM_MODEL, api_key=settings.ANTHROPIC_API_KEY, **kwargs)

    def get_embedding_model(self):
        raise RuntimeError(
            "The anthropic provider has no embeddings endpoint; "
            "set EMBEDDING_PROVIDER=ollama or openai."
        )
