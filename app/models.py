from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class KnowledgeBase:
    id: str
    name: str
    description: str
    created_at: str

    @classmethod
    def new(cls, name: str, description: str = "") -> "KnowledgeBase":
        return cls(
            id=f"kb-{uuid4().hex[:12]}",
            name=name.strip() or "未命名知识库",
            description=description.strip(),
            created_at=now_iso(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeBase":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            created_at=str(data["created_at"]),
        )


@dataclass
class ChatSession:
    id: str
    title: str
    knowledge_base_id: str
    model_id: str
    created_at: str
    updated_at: str

    @classmethod
    def new(cls, knowledge_base_id: str, model_id: str) -> "ChatSession":
        timestamp = now_iso()
        return cls(
            id=f"session-{uuid4().hex[:12]}",
            title="新对话",
            knowledge_base_id=knowledge_base_id,
            model_id=model_id,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatSession":
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "新对话")),
            knowledge_base_id=str(data["knowledge_base_id"]),
            model_id=str(data["model_id"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )


@dataclass
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatMessage":
        return cls(
            role=data["role"],
            content=str(data.get("content", "")),
            citations=list(data.get("citations", [])),
            tool_calls=list(data.get("tool_calls", [])),
        )


@dataclass
class ModelDefinition:
    id: str
    display_name: str
    model_name: str
    local_path: str | None = None
    provider: str = "transformers"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelDefinition":
        return cls(
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            model_name=str(data["model_name"]),
            local_path=data.get("local_path"),
            provider=str(data.get("provider", "transformers")),
        )


@dataclass
class SearchHit:
    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


ChunkingStrategyId = Literal["auto", "custom", "hierarchical"]


@dataclass(frozen=True)
class ChunkingConfig:
    strategy_id: ChunkingStrategyId = "auto"
    delimiter: str = "\n"
    max_length: int = 800
    overlap_percent: int = 10
    normalize_whitespace: bool = True
    remove_urls_emails: bool = False
    preserve_structure: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChunkingConfig":
        strategy_id = data.get("strategy_id", "auto")
        if strategy_id not in {"auto", "custom", "hierarchical"}:
            strategy_id = "auto"
        return cls(
            strategy_id=strategy_id,
            delimiter=str(data.get("delimiter", "\n")),
            max_length=int(data.get("max_length", 800)),
            overlap_percent=int(data.get("overlap_percent", 10)),
            normalize_whitespace=bool(data.get("normalize_whitespace", True)),
            remove_urls_emails=bool(data.get("remove_urls_emails", False)),
            preserve_structure=bool(data.get("preserve_structure", True)),
        )


@dataclass
class DocumentRecord:
    id: str
    knowledge_base_id: str
    file_name: str
    file_hash: str
    source_path: str
    status: Literal["processing", "ready", "failed"]
    chunk_count: int
    config: ChunkingConfig
    error: str | None
    fallback_message: str | None
    created_at: str
    updated_at: str

    @classmethod
    def new(
        cls,
        knowledge_base_id: str,
        file_name: str,
        file_hash: str,
        config: ChunkingConfig,
        source_path: str = "",
    ) -> "DocumentRecord":
        timestamp = now_iso()
        return cls(
            id=f"doc-{uuid4().hex[:12]}",
            knowledge_base_id=knowledge_base_id,
            file_name=file_name,
            file_hash=file_hash,
            source_path=source_path,
            status="processing",
            chunk_count=0,
            config=config,
            error=None,
            fallback_message=None,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["config"] = self.config.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentRecord":
        status = data.get("status", "failed")
        if status not in {"processing", "ready", "failed"}:
            status = "failed"
        return cls(
            id=str(data["id"]),
            knowledge_base_id=str(data["knowledge_base_id"]),
            file_name=str(data["file_name"]),
            file_hash=str(data["file_hash"]),
            source_path=str(data.get("source_path", "")),
            status=status,
            chunk_count=int(data.get("chunk_count", 0)),
            config=ChunkingConfig.from_dict(dict(data.get("config", {}))),
            error=data.get("error"),
            fallback_message=data.get("fallback_message"),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )
