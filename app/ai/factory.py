"""Provider factory: the single place that maps settings -> provider class."""

from app.ai.base import AIProvider
from app.ai.providers import AnthropicProvider, OllamaProvider, OpenAIProvider
from app.config import settings

CHAT_PROVIDERS: dict[str, type[AIProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}

EMBEDDING_PROVIDERS: dict[str, type[AIProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
}


def get_llm_provider() -> AIProvider:
    name = settings.LLM_PROVIDER.strip().lower()
    try:
        return CHAT_PROVIDERS[name]()
    except KeyError:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
            f"Valid options: {sorted(CHAT_PROVIDERS)}."
        ) from None


def get_embedding_provider() -> AIProvider:
    name = settings.EMBEDDING_PROVIDER.strip().lower()
    try:
        return EMBEDDING_PROVIDERS[name]()
    except KeyError:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER '{settings.EMBEDDING_PROVIDER}'. "
            f"Valid options: {sorted(EMBEDDING_PROVIDERS)}."
        ) from None
