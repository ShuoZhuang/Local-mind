from __future__ import annotations

from typing import Iterable, Mapping, Sequence

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
        return self.search_many([knowledge_base_id], query, top_k=top_k)

    def search_many(
        self,
        knowledge_base_ids: Sequence[str],
        query: str,
        top_k: int = 5,
        knowledge_base_names: Mapping[str, str] | None = None,
    ) -> list[SearchHit]:
        if not query.strip() or top_k <= 0:
            return []
        ids = list(dict.fromkeys(str(item).strip() for item in knowledge_base_ids if str(item).strip()))
        if not ids:
            return []
        stores = []
        for knowledge_base_id in ids:
            try:
                store = self.store_factory(knowledge_base_id)
                if store.count:
                    stores.append((knowledge_base_id, store))
            except Exception:
                continue
        if not stores:
            return []
        vector = self.embedder.encode_query(query)
        merged: list[SearchHit] = []
        for knowledge_base_id, store in stores:
            try:
                hits = store.query(vector, top_k=top_k)
            except Exception:
                continue
            for hit in hits:
                metadata = dict(hit.metadata)
                metadata.setdefault("knowledge_base_id", knowledge_base_id)
                if knowledge_base_names and knowledge_base_id in knowledge_base_names:
                    metadata.setdefault("knowledge_base_name", knowledge_base_names[knowledge_base_id])
                merged.append(SearchHit(hit.id, hit.text, hit.score, metadata))
        return rank_by_similarity(merged, top_k=top_k)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
