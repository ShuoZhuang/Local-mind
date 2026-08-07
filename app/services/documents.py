from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.models import DocumentChunk
from app.services.chunking import ExtractedSection

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}


class UnsupportedDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class SplitOptions:
    """Controls how an uploaded document is turned into searchable chunks."""

    mode: Literal["auto", "manual"] = "auto"
    delimiter: str = "\n"
    max_length: int = 800
    overlap_percent: int = 10
    normalize_whitespace: bool = True
    remove_urls_emails: bool = False

    def validate(self) -> None:
        if self.mode not in {"auto", "manual"}:
            raise ValueError("分割模式必须是 auto 或 manual")
        if self.mode == "manual" and not self.delimiter:
            raise ValueError("手动分割的分段标识符不能为空")
        if self.max_length <= 0:
            raise ValueError("分段最大长度必须大于 0")
        if not 0 <= self.overlap_percent < 100:
            raise ValueError("分段重叠度必须在 0 到 99 之间")

    @property
    def overlap_length(self) -> int:
        return int(self.max_length * self.overlap_percent / 100)


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_sections_from_text(text: str, suffix: str) -> list[ExtractedSection]:
    if suffix.lower() not in {".md", ".markdown"}:
        return [ExtractedSection(None, text)]

    sections: list[ExtractedSection] = []
    headings: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        value = "\n".join(buffer).strip()
        if value:
            sections.append(ExtractedSection(None, value, tuple(headings)))
        buffer.clear()

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        title = match.group(2)
        headings[:] = headings[: level - 1]
        headings.append(title)
    flush()
    return sections or [ExtractedSection(None, text)]


def extract_sections(path: Path) -> list[ExtractedSection]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        text = _read_text_file(path)
        text = re.sub(r"^---.*?---", "", text, flags=re.DOTALL)
        text = re.sub(r"```", "", text)
        return extract_sections_from_text(text, suffix)
    return [ExtractedSection(page, text) for page, text in extract_text(path)]


def extract_text(path: Path) -> list[tuple[int | None, str]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentError(f"不支持的文件格式: {suffix or '无扩展名'}")

    if suffix in {".txt", ".md", ".markdown"}:
        text = _read_text_file(path)
        if suffix in {".md", ".markdown"}:
            text = re.sub(r"^---.*?---", "", text, flags=re.DOTALL)
            text = re.sub(r"```", "", text)
        return [(None, text)]

    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("处理 PDF 需要安装 PyMuPDF") from exc
        with fitz.open(path) as document:
            return [(index + 1, page.get_text()) for index, page in enumerate(document)]

    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("处理 DOCX 需要安装 python-docx") from exc
    document = Document(path)
    return [(None, "\n".join(paragraph.text for paragraph in document.paragraphs))]


def _preprocess_piece(text: str, options: SplitOptions) -> str:
    value = text
    if options.remove_urls_emails:
        value = re.sub(r"https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "", value)
    if options.normalize_whitespace:
        value = re.sub(r"\s+", " ", value)
    return value.strip()


def _fixed_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _manual_chunks(text: str, options: SplitOptions) -> list[str]:
    parts = [_preprocess_piece(part, options) for part in text.split(options.delimiter)]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("文本为空，无法建立知识片段")

    chunks: list[str] = []
    overlap = options.overlap_length
    for part in parts:
        if len(part) > options.max_length:
            chunks.extend(_fixed_chunks(part, options.max_length, overlap))
        else:
            chunks.append(part)
    return chunks


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
    options: SplitOptions | None = None,
) -> list[str]:
    if options is not None:
        options.validate()
        if options.mode == "manual":
            return _manual_chunks(text, options)
        text = _preprocess_piece(text, options)

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        raise ValueError("文本为空，无法建立知识片段")
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size 必须大于 overlap，且都应为有效数字")

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        if end < len(cleaned):
            split_at = cleaned.rfind(" ", start, end)
            if split_at > start + chunk_size // 2:
                end = split_at
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def ingest_file(
    path: Path,
    knowledge_base_id: str,
    split_options: SplitOptions | None = None,
) -> list[DocumentChunk]:
    path = Path(path)
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    chunks: list[DocumentChunk] = []
    chunk_index = 0
    for page, text in extract_text(path):
        for piece in chunk_text(text, options=split_options):
            chunk_id = f"{file_hash[:16]}-{chunk_index:04d}"
            metadata = {
                "knowledge_base_id": knowledge_base_id,
                "document_hash": file_hash,
                "source": str(path),
                "file_name": path.name,
                "chunk_index": chunk_index,
            }
            if page is not None:
                metadata["page"] = page
            chunks.append(DocumentChunk(chunk_id, piece, metadata))
            chunk_index += 1
    if not chunks:
        raise ValueError("文件中没有可用文本")
    return chunks
