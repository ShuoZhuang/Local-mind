from app.services.vector_store import KnowledgeBaseVectorStore


class FakeCollection:
    def __init__(self):
        self.where = None
        self.deleted_ids = None
        self.ids = ["chunk-1", "chunk-2"]

    def delete(self, ids):
        self.deleted_ids = ids
        self.ids = [identifier for identifier in self.ids if identifier not in ids]

    def get(self, where=None, include=None, ids=None):
        if ids is not None:
            return {"ids": [identifier for identifier in ids if identifier in self.ids]}
        if where is not None:
            self.where = where
        remaining = [identifier for identifier in self.ids]
        return {
            "ids": remaining,
            "documents": ["第一段" if identifier == "chunk-1" else "第二段" for identifier in remaining],
            "metadatas": [{"chunk_index": 0 if identifier == "chunk-1" else 1} for identifier in remaining],
        }


def test_delete_document_removes_chunks_by_document_id():
    store = KnowledgeBaseVectorStore.__new__(KnowledgeBaseVectorStore)
    store.collection = FakeCollection()

    store.delete_document("doc-123")

    assert store.collection.where == {"document_id": "doc-123"}
    assert store.collection.deleted_ids == ["chunk-1", "chunk-2"]


def test_get_document_chunks_returns_ordered_chunk_preview():
    store = KnowledgeBaseVectorStore.__new__(KnowledgeBaseVectorStore)
    store.collection = FakeCollection()

    chunks = store.get_document_chunks("doc-123")

    assert store.collection.where == {"document_id": "doc-123"}
    assert [chunk.text for chunk in chunks] == ["第一段", "第二段"]


def test_delete_chunk_removes_only_requested_vector():
    store = KnowledgeBaseVectorStore.__new__(KnowledgeBaseVectorStore)
    store.collection = FakeCollection()

    assert store.delete_chunk("chunk-1") is True
    assert store.collection.deleted_ids == ["chunk-1"]
    assert [chunk.id for chunk in store.get_document_chunks("doc-123")] == ["chunk-2"]
    assert store.delete_chunk("missing") is False
