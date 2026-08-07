from __future__ import annotations

from pathlib import Path

from app.models import DocumentChunk, SearchHit


class KnowledgeBaseVectorStore:
    def __init__(self, db_path: Path, knowledge_base_id: str):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("向量库需要安装 chromadb") from exc
        self.collection_name = f"kb_{knowledge_base_id}"
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return int(self.collection.count())

    def upsert(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError("文档片段和向量数量不一致")
        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=vectors,
            metadatas=[chunk.metadata for chunk in chunks],
        )

    def delete_document(self, document_id: str) -> None:
        """删除一个文档当前拥有的全部片段向量。"""
        found = self.collection.get(where={"document_id": document_id})
        ids = found.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)

    def get_document_chunks(self, document_id: str) -> list[DocumentChunk]:
        result = self.collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
        )
        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        chunks = [
            DocumentChunk(identifier, text, metadata or {})
            for identifier, text, metadata in zip(ids, documents, metadatas)
        ]
        return sorted(chunks, key=lambda chunk: int(chunk.metadata.get("chunk_index", 0)))

    def query(self, vector: list[float], top_k: int = 5) -> list[SearchHit]:
        if top_k <= 0 or self.count == 0:
            return []
        result = self.collection.query(query_embeddings=[vector], n_results=min(top_k, self.count))
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            SearchHit(
                id=identifier,
                text=text,
                score=1.0 - float(distance),
                metadata=metadata or {},
            )
            for identifier, text, metadata, distance in zip(ids, documents, metadatas, distances)
        ]
