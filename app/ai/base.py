from typing import Protocol

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel


class AIProvider(Protocol):
    """A thin provider interface: build the LangChain chat/embedding models.

    Implementations live in app/ai/providers.py and only instantiate the
    matching LangChain classes — no extra behaviour hides behind this.
    """

    name: str

    def get_chat_model(self, **kwargs) -> BaseChatModel: ...

    def get_embedding_model(self) -> Embeddings: ...
