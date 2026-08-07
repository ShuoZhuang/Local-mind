from app.services.vector_store import KnowledgeBaseVectorStore


class FakeCollection:
    def __init__(self):
        self.where = None
        self.deleted_ids = None

    def get(self, where):
        self.where = where
        return {"ids": ["chunk-1", "chunk-2"]}

    def delete(self, ids):
        self.deleted_ids = ids

    def get(self, where=None, include=None):
        if where is not None:
            self.where = where
        return {
            "ids": ["chunk-1", "chunk-2"],
            "documents": ["第一段", "第二段"],
            "metadatas": [{"chunk_index": 0}, {"chunk_index": 1}],
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
