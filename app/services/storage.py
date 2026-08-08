from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import (
    ChunkingConfig,
    ChatMessage,
    ChatSession,
    DocumentRecord,
    KnowledgeBase,
    MCPServerDefinition,
    now_iso,
)


class LocalStateStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.knowledge_bases_path = self.root / "knowledge_bases.json"
        self.sessions_path = self.root / "sessions.json"
        self.documents_path = self.root / "documents.json"
        self.chunking_default_path = self.root / "chunking_default.json"
        self.settings_path = self.root / "settings.json"
        self.mcp_servers_path = self.root / "mcp_servers.json"

    def load_preheat_models(self) -> bool:
        return bool(self._read_json(self.settings_path, {}).get("preheat_models", False))

    def save_preheat_models(self, enabled: bool) -> None:
        settings = self._read_json(self.settings_path, {})
        settings["preheat_models"] = bool(enabled)
        self._write_json(self.settings_path, settings)

    def list_mcp_servers(self) -> list[MCPServerDefinition]:
        servers: list[MCPServerDefinition] = []
        for item in self._read_json(self.mcp_servers_path, []):
            if not isinstance(item, dict):
                continue
            try:
                servers.append(MCPServerDefinition.from_dict(item))
            except (KeyError, TypeError, ValueError):
                continue
        return servers

    def save_mcp_server(self, server: MCPServerDefinition) -> None:
        if not server.command.strip():
            raise ValueError("MCP 服务命令不能为空")
        server.updated_at = now_iso()
        servers = {item.id: item for item in self.list_mcp_servers()}
        servers[server.id] = server
        self._write_json(self.mcp_servers_path, [item.to_dict() for item in servers.values()])

    def delete_mcp_server(self, server_id: str) -> None:
        servers = [item for item in self.list_mcp_servers() if item.id != server_id]
        self._write_json(self.mcp_servers_path, [item.to_dict() for item in servers])

    def create_knowledge_base(self, name: str, description: str = "") -> KnowledgeBase:
        item = KnowledgeBase.new(name, description)
        items = self.list_knowledge_bases()
        items.append(item)
        self._write_json(self.knowledge_bases_path, [value.to_dict() for value in items])
        return item

    def list_knowledge_bases(self) -> list[KnowledgeBase]:
        return [KnowledgeBase.from_dict(item) for item in self._read_json(self.knowledge_bases_path, [])]

    def delete_knowledge_base(self, knowledge_base_id: str) -> None:
        items = [item for item in self.list_knowledge_bases() if item.id != knowledge_base_id]
        self._write_json(self.knowledge_bases_path, [item.to_dict() for item in items])

    def delete_documents_for_knowledge_base(self, knowledge_base_id: str) -> None:
        records = [
            item
            for item in self._read_json(self.documents_path, [])
            if item.get("knowledge_base_id") != knowledge_base_id
        ]
        self._write_json(self.documents_path, records)

    def delete_sessions_for_knowledge_base(self, knowledge_base_id: str) -> None:
        for session in self.list_sessions():
            if knowledge_base_id in session.selected_knowledge_base_ids():
                self.delete_session(session.id)

    def rename_knowledge_base(self, knowledge_base_id: str, name: str) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("知识库名称不能为空")
        items = self.list_knowledge_bases()
        for item in items:
            if item.id == knowledge_base_id:
                item.name = clean_name
                self._write_json(self.knowledge_bases_path, [value.to_dict() for value in items])
                return
        raise KeyError(f"知识库不存在: {knowledge_base_id}")

    def save_session(self, session: ChatSession, messages: list[ChatMessage]) -> None:
        sessions = {
            item["id"]: item for item in self._read_json(self.sessions_path, [])
        }
        sessions[session.id] = session.to_dict()
        self._write_json(self.sessions_path, list(sessions.values()))
        self._write_json(
            self.root / f"session_{session.id}.json",
            {"session": session.to_dict(), "messages": [message.to_dict() for message in messages]},
        )

    def list_sessions(self) -> list[ChatSession]:
        items = [ChatSession.from_dict(item) for item in self._read_json(self.sessions_path, [])]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def load_session(self, session_id: str) -> tuple[ChatSession, list[ChatMessage]]:
        data = self._read_json(self.root / f"session_{session_id}.json", {})
        if not data:
            raise FileNotFoundError(f"会话不存在: {session_id}")
        session = ChatSession.from_dict(data["session"])
        return session, [ChatMessage.from_dict(item) for item in data.get("messages", [])]

    def update_session_title(self, session_id: str, title: str) -> None:
        session, messages = self.load_session(session_id)
        session.title = title.strip() or "新对话"
        session.updated_at = now_iso()
        self.save_session(session, messages)

    def delete_session(self, session_id: str) -> None:
        sessions = [
            item for item in self._read_json(self.sessions_path, []) if item.get("id") != session_id
        ]
        self._write_json(self.sessions_path, sessions)
        path = self.root / f"session_{session_id}.json"
        if path.exists():
            path.unlink()

    def list_documents(self, knowledge_base_id: str) -> list[DocumentRecord]:
        records = [
            DocumentRecord.from_dict(item)
            for item in self._read_json(self.documents_path, [])
            if item.get("knowledge_base_id") == knowledge_base_id
        ]
        return sorted(records, key=lambda record: record.updated_at, reverse=True)

    def save_document(self, record: DocumentRecord) -> None:
        records = [DocumentRecord.from_dict(item) for item in self._read_json(self.documents_path, [])]
        by_id = {item.id: item for item in records}
        by_id[record.id] = record
        self._write_json(self.documents_path, [item.to_dict() for item in by_id.values()])

    def get_document(self, document_id: str) -> DocumentRecord:
        for item in self._read_json(self.documents_path, []):
            if item.get("id") == document_id:
                return DocumentRecord.from_dict(item)
        raise KeyError(f"文档不存在: {document_id}")

    def delete_document_record(self, document_id: str) -> None:
        records = [
            item for item in self._read_json(self.documents_path, []) if item.get("id") != document_id
        ]
        self._write_json(self.documents_path, records)

    def recover_stale_processing_documents(self) -> int:
        records = [
            DocumentRecord.from_dict(item)
            for item in self._read_json(self.documents_path, [])
        ]
        recovered = 0
        for record in records:
            if record.status == "processing":
                record.status = "failed"
                record.error = "上一次处理未完成，请重新处理该文档。"
                record.updated_at = now_iso()
                recovered += 1
        if recovered:
            self._write_json(self.documents_path, [record.to_dict() for record in records])
        return recovered

    def load_chunking_default(self) -> ChunkingConfig:
        value = self._read_json(self.chunking_default_path, {})
        if not isinstance(value, dict):
            return ChunkingConfig()
        try:
            return ChunkingConfig.from_dict(value)
        except (TypeError, ValueError):
            return ChunkingConfig()

    def save_chunking_default(self, config: ChunkingConfig) -> None:
        self._write_json(self.chunking_default_path, config.to_dict())

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            broken = path.with_suffix(path.suffix + ".broken")
            try:
                path.replace(broken)
            except OSError:
                pass
            return default

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
