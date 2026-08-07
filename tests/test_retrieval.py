from app.models import SearchHit
from app.services.retrieval import rank_by_similarity
from app.services.retrieval import RetrievalService


def test_rank_by_similarity_sorts_descending_and_limits_top_k():
    items = [
        SearchHit("b", "second", 0.8, {}),
        SearchHit("a", "first", 0.8, {}),
        SearchHit("c", "third", 0.2, {}),
    ]

    results = rank_by_similarity(items, top_k=2)

    assert [item.id for item in results] == ["a", "b"]


def test_rank_by_similarity_returns_empty_for_non_positive_top_k():
    assert rank_by_similarity([SearchHit("a", "text", 1.0, {})], top_k=0) == []
    assert rank_by_similarity([SearchHit("a", "text", 1.0, {})], top_k=-1) == []


def test_empty_store_does_not_encode_query():
    class EmptyStore:
        count = 0

    class FailingEmbedder:
        def encode_query(self, query):
            raise AssertionError("空知识库不应该加载 Embedding")

    service = RetrievalService(FailingEmbedder(), lambda _knowledge_base_id: EmptyStore())

    assert service.search("kb-empty", "普通聊天") == []


def test_search_many_encodes_once_merges_and_marks_knowledge_base():
    class Store:
        def __init__(self, hits):
            self.hits = hits
            self.count = len(hits)

        def query(self, vector, top_k=5):
            return self.hits[:top_k]

    stores = {
        "kb-ai": Store([SearchHit("ai-1", "Embedding", 0.82, {"file_name": "ai.md"})]),
        "kb-rag": Store([SearchHit("rag-1", "RAG", 0.94, {"file_name": "rag.md"})]),
    }

    class Embedder:
        def __init__(self):
            self.calls = []

        def encode_query(self, query):
            self.calls.append(query)
            return [1.0, 0.0]

    embedder = Embedder()
    service = RetrievalService(embedder, stores.__getitem__)

    results = service.search_many(
        ["kb-ai", "kb-rag"],
        "怎么检索？",
        top_k=2,
        knowledge_base_names={"kb-ai": "AI 笔记", "kb-rag": "RAG 笔记"},
    )

    assert embedder.calls == ["怎么检索？"]
    assert [hit.id for hit in results] == ["rag-1", "ai-1"]
    assert results[0].metadata["knowledge_base_id"] == "kb-rag"
    assert results[0].metadata["knowledge_base_name"] == "RAG 笔记"


def test_search_many_skips_empty_and_failed_stores():
    class EmptyStore:
        count = 0

    class BrokenStore:
        count = 1

        def query(self, vector, top_k=5):
            raise RuntimeError("store unavailable")

    class Embedder:
        def encode_query(self, query):
            return [1.0]

    stores = {"empty": EmptyStore(), "broken": BrokenStore()}
    service = RetrievalService(Embedder(), stores.__getitem__)

    assert service.search_many(["empty", "broken"], "query") == []
