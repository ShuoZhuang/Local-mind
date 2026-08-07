from __future__ import annotations

from typing import Iterable, Sequence

from app.models import SearchHit


def rank_by_similarity(items: Iterable[SearchHit], top_k: int = 5) -> list[SearchHit]:
    if top_k <= 0:
        return []
    return sorted(items, key=lambda item: (-item.score, item.id))[:top_k]


class RetrievalService:
    def __init__(self, embedder, store_factory):
        self.embedder = embedder
        self.store_factory = store_factory

    def search(self, knowledge_base_id: str, query: str, top_k: int = 5) -> list[SearchHit]:
        if not query.strip() or top_k <= 0:
            return []
        store = self.store_factory(knowledge_base_id)
        if store.count == 0:
            return []
        vector = self.embedder.encode_query(query)
        return store.query(vector, top_k=top_k)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
