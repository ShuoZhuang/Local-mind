from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models import ChunkingConfig, DocumentChunk, DocumentRecord, now_iso
from app.services.chunking import build_chunker
from app.services.documents import SplitOptions, extract_sections, ingest_file


@dataclass(frozen=True)
class IngestionResult:
    record: DocumentRecord
    chunks: list[DocumentChunk]


class KnowledgeBaseService:
    def __init__(self, embedder, store_factory, documents_dir: Path | None = None):
        self.embedder = embedder
        self.store_factory = store_factory
        self.documents_dir = Path(documents_dir) if documents_dir else None

    def import_file(
        self,
        path: Path,
        knowledge_base_id: str,
        progress_callback: Callable[[tuple[str, int]], None] | None = None,
        split_options: SplitOptions | None = None,
    ) -> list[DocumentChunk]:
        self._report(progress_callback, "extracting", 0)
        chunks = ingest_file(path, knowledge_base_id, split_options=split_options)
        self._report(progress_callback, "embedding", 40)
        vectors = self.embedder.encode_documents([chunk.text for chunk in chunks])
        self._report(progress_callback, "saving", 80)
        self.store_factory(knowledge_base_id).upsert(chunks, vectors)
        self._copy_original(path, knowledge_base_id)
        self._report(progress_callback, "done", 100)
        return chunks

    def reprocess_file(
        self,
        path: Path,
        record: DocumentRecord,
        progress_callback: Callable[[tuple[str, int]], None] | None = None,
    ) -> IngestionResult:
        path = Path(path)
        self._report(progress_callback, "extracting", 0)
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        chunking_result = build_chunker(record.config).split(extract_sections(path))
        chunks: list[DocumentChunk] = []
        for index, piece in enumerate(chunking_result.pieces):
            metadata = {
                "knowledge_base_id": record.knowledge_base_id,
                "document_id": record.id,
                "document_hash": file_hash,
                "source": str(path),
                "file_name": path.name,
                "chunk_index": index,
            }
            if piece.page is not None:
                metadata["page"] = piece.page
            if piece.heading_path:
                metadata["heading_path"] = " > ".join(piece.heading_path)
            chunks.append(DocumentChunk(f"{file_hash[:16]}-{index:04d}", piece.text, metadata))

        self._report(progress_callback, "embedding", 40)
        vectors = self.embedder.encode_documents([chunk.text for chunk in chunks])
        self._report(progress_callback, "embedding_done", 60)
        store = self.store_factory(record.knowledge_base_id)
        self._report(progress_callback, "deleting_old", 70)
        store.delete_document(record.id)
        self._report(progress_callback, "saving", 80)
        store.upsert(chunks, vectors)
        self._report(progress_callback, "saved", 95)
        copied_path = self._copy_original(path, record.knowledge_base_id)
        record.file_hash = file_hash
        record.file_name = path.name
        record.source_path = str(copied_path or path)
        record.status = "ready"
        record.chunk_count = len(chunks)
        record.error = None
        record.fallback_message = chunking_result.fallback_message
        record.updated_at = now_iso()
        self._report(progress_callback, "done", 100)
        return IngestionResult(record, chunks)

    def _copy_original(self, path: Path, knowledge_base_id: str) -> Path | None:
        if self.documents_dir is None:
            return None
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        safe_name = re.sub(r"[^\w.\-一-龥]", "_", path.name)
        target_dir = self.documents_dir / knowledge_base_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{file_hash}_{safe_name}"
        if not target.exists():
            shutil.copy2(path, target)
        return target

    @staticmethod
    def _report(callback, stage: str, progress: int) -> None:
        if callback:
            callback((stage, progress))
