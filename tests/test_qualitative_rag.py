from langchain_core.embeddings import Embeddings

from app.tools import qualitative_rag as rag


class CountingEmbeddings(Embeddings):
    def __init__(self):
        self.texts = 0

    def embed_documents(self, texts):
        self.texts += len(texts)
        return [[float(len(t)), 1.0] for t in texts]

    def embed_query(self, text):
        self.texts += 1
        return [float(len(text)), 1.0]


def _tool(monkeypatch, emb):
    provider = type("P", (), {"get_embedding_model": lambda self: emb})()
    monkeypatch.setattr(rag, "get_embedding_provider", lambda: provider)
    return rag.QualitativeAnalysisTool()


def test_index_stays_within_the_embedding_quota(monkeypatch):
    emb = CountingEmbeddings()
    sentence = "Management expects deal momentum to continue into the next quarter. "
    monkeypatch.setattr(rag, "_pdf_text", lambda path: f"{path}: " + sentence * 1000)  # ~70 chunks each
    tool = _tool(monkeypatch, emb)
    tool.build_index(["newest.pdf", "older.pdf", "oldest.pdf"])
    assert emb.texts == rag.MAX_CHUNKS
    # Newest first: the latest call is whole, the oldest is left out.
    indexed = " ".join(d.page_content for d in tool.vdb.docstore._dict.values())
    assert "newest.pdf" in indexed and "oldest.pdf" not in indexed


def test_small_index_is_kept_whole(monkeypatch):
    emb = CountingEmbeddings()
    monkeypatch.setattr(rag, "_pdf_text", lambda path: "Margins held at 24.5% despite wage hikes.")
    _tool(monkeypatch, emb).build_index(["t.pdf"])
    assert emb.texts == 1
