from typing import Any

import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from app.ai.factory import get_embedding_provider
from app.utils.logger import get_logger
from app.utils.text import clean_text

log = get_logger("QualitativeAnalysisTool")

def _pdf_text(path: str) -> str:
    texts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return clean_text("\n".join(texts))

class QualitativeAnalysisTool:
    """RAG over earning call transcripts using configurable embeddings + FAISS."""
    def __init__(self):
        self.emb = get_embedding_provider().get_embedding_model()
        self.vdb = None

    def build_index(self, transcript_paths: list[str]):
        all_text = []
        for p in transcript_paths:
            try:
                all_text.append(_pdf_text(p))
            except Exception as e:
                log.error(f"Transcript read failed {p}: {e}")

        splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
        docs = splitter.create_documents(all_text)
        self.vdb = FAISS.from_documents(docs, self.emb)

    def query_themes(self, queries: list[str], k=5) -> dict[str, Any]:
        if self.vdb is None:
            return {}
        out = {}
        for q in queries:
            docs = self.vdb.similarity_search(q, k=k)
            out[q] = [d.page_content for d in docs]
        return out
