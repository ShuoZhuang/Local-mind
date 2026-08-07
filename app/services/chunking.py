from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.models import ChunkingConfig


@dataclass(frozen=True)
class ExtractedSection:
    page: int | None
    text: str
    heading_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkPiece:
    text: str
    page: int | None
    heading_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkingResult:
    pieces: list[ChunkPiece]
    fallback_message: str | None = None


class ChunkingStrategy(Protocol):
    def split(self, sections: list[ExtractedSection]) -> ChunkingResult:
        raise NotImplementedError


def _clean(text: str, config: ChunkingConfig) -> str:
    value = text
    if config.remove_urls_emails:
        value = re.sub(r"https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "", value)
    if config.normalize_whitespace:
        value = re.sub(r"\s+", " ", value)
    return value.strip()


def _fixed_chunks(text: str, config: ChunkingConfig) -> list[str]:
    overlap = int(config.max_length * config.overlap_percent / 100)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + config.max_length, len(text))
        if end < len(text):
            split_at = text.rfind(" ", start, end)
            if split_at > start + config.max_length // 2:
                end = split_at
        value = text[start:end].strip()
        if value:
            chunks.append(value)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


class AutoChunker:
    def __init__(self, config: ChunkingConfig):
        self.config = config

    def split(self, sections: list[ExtractedSection]) -> ChunkingResult:
        pieces: list[ChunkPiece] = []
        for section in sections:
            value = _clean(section.text, self.config)
            if not value:
                continue
            for chunk in _fixed_chunks(value, self.config):
                pieces.append(ChunkPiece(chunk, section.page, section.heading_path))
        if not pieces:
            raise ValueError("文本为空，无法建立知识片段")
        return ChunkingResult(pieces)


class CustomChunker:
    def __init__(self, config: ChunkingConfig):
        self.config = config

    def split(self, sections: list[ExtractedSection]) -> ChunkingResult:
        if not self.config.delimiter:
            raise ValueError("自定义分段的分隔符不能为空")
        pieces: list[ChunkPiece] = []
        for section in sections:
            for raw_part in section.text.split(self.config.delimiter):
                value = _clean(raw_part, self.config)
                if not value:
                    continue
                for chunk in _fixed_chunks(value, self.config):
                    pieces.append(ChunkPiece(chunk, section.page, section.heading_path))
        if not pieces:
            raise ValueError("文本为空，无法建立知识片段")
        return ChunkingResult(pieces)


class HierarchicalChunker:
    def __init__(self, config: ChunkingConfig):
        self.config = config
        self._auto = AutoChunker(config)

    def split(self, sections: list[ExtractedSection]) -> ChunkingResult:
        result = self._auto.split(sections)
        if any(piece.heading_path for piece in result.pieces):
            return result
        return ChunkingResult(result.pieces, "未识别到明确层级，已使用自动分段。")


def build_chunker(config: ChunkingConfig) -> ChunkingStrategy:
    if config.max_length <= 0:
        raise ValueError("分段最大长度必须大于 0")
    if not 0 <= config.overlap_percent < 100:
        raise ValueError("分段重叠度必须在 0 到 99 之间")
    if config.strategy_id == "custom":
        return CustomChunker(config)
    if config.strategy_id == "hierarchical":
        return HierarchicalChunker(config)
    return AutoChunker(config)
