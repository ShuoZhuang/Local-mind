from pathlib import Path

from app.models import ChunkingConfig, DocumentRecord
from app.services.ingestion import KnowledgeBaseService
from app.services.documents import SplitOptions


class FakeEmbedder:
    def encode_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]


class FakeStore:
    def __init__(self):
        self.saved = []

    def upsert(self, chunks, vectors):
        self.saved.extend(zip(chunks, vectors))

    def delete_document(self, document_id):
        return None


def test_import_file_reports_progress_and_saves_vectors(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("Embedding 把文本转换成向量。", encoding="utf-8")
    store = FakeStore()
    progress = []
    service = KnowledgeBaseService(FakeEmbedder(), lambda _: store)

    chunks = service.import_file(source, "kb-ai", progress.append)

    assert chunks
    assert len(store.saved) == len(chunks)
    assert progress[0] == ("extracting", 0)
    assert progress[-1] == ("done", 100)


def test_import_file_passes_split_options_to_ingestion(tmp_path):
    source = tmp_path / "note.txt"
    source.write_text("第一段|第二段", encoding="utf-8")
    store = FakeStore()
    options = SplitOptions(mode="manual", delimiter="|", max_length=800, overlap_percent=0)
    service = KnowledgeBaseService(FakeEmbedder(), lambda _: store)

    chunks = service.import_file(source, "kb-ai", split_options=options)

    assert [chunk.text for chunk in chunks] == ["第一段", "第二段"]


def test_reprocess_deletes_old_vectors_before_upserting_new_ones(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# 标题\n正文", encoding="utf-8")
    calls = []

    class RecordingStore(FakeStore):
        def delete_document(self, document_id):
            calls.append(("delete_document", document_id))

        def upsert(self, chunks, vectors):
            calls.append(("upsert", len(chunks)))
            super().upsert(chunks, vectors)

    record = DocumentRecord.new("kb-ai", source.name, "old-hash", ChunkingConfig())
    service = KnowledgeBaseService(FakeEmbedder(), lambda _: RecordingStore())

    result = service.reprocess_file(source, record)

    assert calls[0] == ("delete_document", record.id)
    assert calls[-1][0] == "upsert"
    assert result.record.status == "ready"
    assert result.chunks[0].metadata["document_id"] == record.id


def test_reprocess_records_the_local_copy_path(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# 标题\n正文", encoding="utf-8")
    record = DocumentRecord.new("kb-ai", source.name, "old-hash", ChunkingConfig())
    service = KnowledgeBaseService(FakeEmbedder(), lambda _: FakeStore(), tmp_path / "documents")

    result = service.reprocess_file(source, record)

    copied_path = tmp_path / "documents" / "kb-ai" / result.record.source_path.split("\\")[-1]
    assert Path(result.record.source_path).exists()
    assert Path(result.record.source_path).parent == copied_path.parent


def test_reprocess_reports_embedding_and_storage_boundaries(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# 标题\n正文", encoding="utf-8")
    events = []
    record = DocumentRecord.new("kb-ai", source.name, "old-hash", ChunkingConfig())
    service = KnowledgeBaseService(FakeEmbedder(), lambda _: FakeStore())

    service.reprocess_file(source, record, events.append)

    assert [stage for stage, _ in events] == [
        "extracting", "embedding", "embedding_done", "deleting_old", "saving", "saved", "done"
    ]
