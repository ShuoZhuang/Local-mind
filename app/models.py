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
    knowledge_base_ids: list[str] = field(default_factory=list)

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
            knowledge_base_ids=[knowledge_base_id],
        )

    def selected_knowledge_base_ids(self) -> list[str]:
        candidates = self.knowledge_base_ids or [self.knowledge_base_id]
        return list(dict.fromkeys(str(item).strip() for item in candidates if str(item).strip()))

    def set_knowledge_base_ids(self, ids: list[str]) -> None:
        cleaned = list(dict.fromkeys(str(item).strip() for item in ids if str(item).strip()))
        if not cleaned:
            raise ValueError("至少选择一个知识库")
        self.knowledge_base_ids = cleaned
        self.knowledge_base_id = cleaned[0]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatSession":
        legacy_id = str(data["knowledge_base_id"])
        selected_ids = data.get("knowledge_base_ids") or [legacy_id]
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "新对话")),
            knowledge_base_id=legacy_id,
            model_id=str(data["model_id"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            knowledge_base_ids=list(selected_ids),
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
class MCPServerDefinition:
    """A user-approved local stdio MCP server configuration."""

    id: str
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def new(
        cls,
        name: str,
        command: str,
        args: tuple[str, ...] | list[str] = (),
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        enabled: bool = True,
    ) -> "MCPServerDefinition":
        timestamp = now_iso()
        return cls(
            id=f"mcp-{uuid4().hex[:12]}",
            name=str(name).strip() or "未命名 MCP 服务",
            command=str(command).strip(),
            args=[str(value) for value in args],
            cwd=str(cwd).strip() if cwd else None,
            env={str(key): str(value) for key, value in (env or {}).items()},
            enabled=bool(enabled),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPServerDefinition":
        raw_args = data.get("args", [])
        raw_env = data.get("env", {})
        if not isinstance(raw_args, list):
            raw_args = []
        if not isinstance(raw_env, dict):
            raw_env = {}
        created_at = str(data.get("created_at", ""))
        updated_at = str(data.get("updated_at", created_at))
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "未命名 MCP 服务")),
            command=str(data.get("command", "")),
            args=[str(value) for value in raw_args],
            cwd=str(data["cwd"]).strip() if data.get("cwd") else None,
            env={str(key): str(value) for key, value in raw_env.items()},
            enabled=bool(data.get("enabled", True)),
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass(frozen=True)
class MCPToolDisplayMetadata:
    """Optional user-facing text for one discovered MCP tool."""

    server_id: str
    tool_name: str
    display_name: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPToolDisplayMetadata":
        return cls(
            server_id=str(data["server_id"]),
            tool_name=str(data["tool_name"]),
            display_name=str(data.get("display_name", "")).strip(),
            description=str(data.get("description", "")).strip(),
        )


@dataclass(frozen=True)
class ToolContract:
    """Safety and routing contract attached to every model-callable tool."""

    purpose: str = ""
    use_when: tuple[str, ...] = field(default_factory=tuple)
    avoid_when: tuple[str, ...] = field(default_factory=tuple)
    intent_keywords: tuple[str, ...] = field(default_factory=tuple)
    intent_exclusions: tuple[str, ...] = field(default_factory=tuple)
    parameter_rules: tuple[str, ...] = field(default_factory=tuple)
    examples: tuple[str, ...] = field(default_factory=tuple)
    recovery_hint: str = ""
    retry_on_error: bool = False
    configured: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolContract":
        values = dict(data or {})
        return cls(
            purpose=str(values.get("purpose", "")),
            use_when=tuple(str(value) for value in values.get("use_when", []) or []),
            avoid_when=tuple(str(value) for value in values.get("avoid_when", []) or []),
            intent_keywords=tuple(str(value) for value in values.get("intent_keywords", []) or []),
            intent_exclusions=tuple(str(value) for value in values.get("intent_exclusions", []) or []),
            parameter_rules=tuple(str(value) for value in values.get("parameter_rules", []) or []),
            examples=tuple(str(value) for value in values.get("examples", []) or []),
            recovery_hint=str(values.get("recovery_hint", "")),
            retry_on_error=bool(values.get("retry_on_error", False)),
            configured=bool(values.get("configured", True)),
        )


@dataclass(frozen=True)
class ToolDefinition:
    """A card-ready description of a real tool or a local system capability."""

    id: str
    name: str
    category: str
    description: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = False
    icon_text: str = "◇"
    recent_calls: tuple[str, ...] = field(default_factory=tuple)
    kind: str = "tool"
    source: str | None = None
    input_schema: dict[str, Any] = field(default_factory=dict)
    raw_name: str | None = None
    raw_description: str | None = None
    last_error: str | None = None
    contract: ToolContract = field(default_factory=ToolContract)


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
