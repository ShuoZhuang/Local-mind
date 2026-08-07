from pathlib import Path

import pytest

from app.services.documents import (
    SplitOptions,
    UnsupportedDocumentError,
    chunk_text,
    extract_text,
    ingest_file,
)


def test_chunk_text_keeps_overlap_between_long_chunks():
    text = " ".join(f"词{i}" for i in range(30))

    chunks = chunk_text(text, chunk_size=40, overlap=10)

    assert len(chunks) > 1
    assert set(chunks[0].split()) & set(chunks[1].split())


def test_empty_text_is_rejected():
    with pytest.raises(ValueError, match="文本为空"):
        chunk_text("   ")


def test_unsupported_extension_is_rejected(tmp_path):
    path = tmp_path / "notes.xlsx"
    path.write_bytes(b"not supported")

    with pytest.raises(UnsupportedDocumentError):
        extract_text(path)


def test_ingest_text_file_creates_stable_chunks_and_metadata(tmp_path):
    source = tmp_path / "embedding.md"
    source.write_text("Embedding 可以把文本转换成向量。", encoding="utf-8")

    first = ingest_file(source, "kb-ai")
    second = ingest_file(source, "kb-ai")

    assert first[0].id == second[0].id
    assert first[0].metadata["knowledge_base_id"] == "kb-ai"
    assert first[0].metadata["file_name"] == "embedding.md"


def test_manual_split_uses_delimiter_and_overlap_percentage():
    options = SplitOptions(
        mode="manual",
        delimiter="|",
        max_length=12,
        overlap_percent=25,
        normalize_whitespace=False,
    )

    chunks = chunk_text("第一段内容|第二段内容|第三段内容", options=options)

    assert chunks == ["第一段内容", "第二段内容", "第三段内容"]
    assert options.overlap_length == 3

    long_chunks = chunk_text("0123456789ABCDEFGHIJ", options=options)
    assert len(long_chunks) == 2
    assert long_chunks[0][-3:] == long_chunks[1][:3]


def test_manual_split_applies_preprocessing_without_removing_delimiter():
    options = SplitOptions(
        mode="manual",
        delimiter="\n",
        max_length=800,
        overlap_percent=10,
        normalize_whitespace=True,
        remove_urls_emails=True,
    )

    chunks = chunk_text(
        "第一段   文本\n第二段\t文本 联系 me@example.com https://example.com",
        options=options,
    )

    assert len(chunks) == 2
    assert chunks[0] == "第一段 文本"
    assert chunks[1] == "第二段 文本 联系"


def test_ingest_file_accepts_manual_split_options(tmp_path):
    source = tmp_path / "manual.txt"
    source.write_text("A|B|C", encoding="utf-8")
    options = SplitOptions(mode="manual", delimiter="|", max_length=800, overlap_percent=0)

    chunks = ingest_file(source, "kb-manual", split_options=options)

    assert [chunk.text for chunk in chunks] == ["A", "B", "C"]
