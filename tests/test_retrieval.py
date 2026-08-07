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
