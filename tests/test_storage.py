from app.models import (
    ChatMessage,
    ChatSession,
    ChunkingConfig,
    DocumentRecord,
    MCPServerDefinition,
)
from app.services.storage import LocalStateStore


def test_knowledge_bases_persist_in_creation_order(tmp_path):
    store = LocalStateStore(tmp_path)
    first = store.create_knowledge_base("人工智能学习", "Embedding")
    second = store.create_knowledge_base("模电笔记", "三极管")

    reopened = LocalStateStore(tmp_path)

    assert [item.id for item in reopened.list_knowledge_bases()] == [first.id, second.id]


def test_session_and_messages_survive_store_recreation(tmp_path):
    store = LocalStateStore(tmp_path)
    knowledge_base = store.create_knowledge_base("AI")
    session = ChatSession.new(knowledge_base.id, "qwen-1.5b")
    messages = [
        ChatMessage("user", "什么是 Embedding？"),
        ChatMessage("assistant", "Embedding 可以把文本转换成向量。"),
    ]

    store.save_session(session, messages)
    loaded_session, loaded_messages = LocalStateStore(tmp_path).load_session(session.id)

    assert loaded_session.id == session.id
    assert loaded_session.knowledge_base_id == knowledge_base.id
    assert [message.content for message in loaded_messages] == [message.content for message in messages]


def test_deleting_knowledge_base_removes_it_from_state(tmp_path):
    store = LocalStateStore(tmp_path)
    knowledge_base = store.create_knowledge_base("待删除")

    store.delete_knowledge_base(knowledge_base.id)

    assert store.list_knowledge_bases() == []


def test_knowledge_base_can_be_renamed(tmp_path):
    store = LocalStateStore(tmp_path)
    knowledge_base = store.create_knowledge_base("旧名称")

    store.rename_knowledge_base(knowledge_base.id, "学生守则")

    assert store.list_knowledge_bases()[0].name == "学生守则"


def test_session_can_be_deleted_with_its_history(tmp_path):
    store = LocalStateStore(tmp_path)
    knowledge_base = store.create_knowledge_base("AI")
    session = ChatSession.new(knowledge_base.id, "qwen-1.5b")
    store.save_session(session, [ChatMessage("user", "测试")])

    store.delete_session(session.id)

    assert store.list_sessions() == []
    assert not (tmp_path / f"session_{session.id}.json").exists()


def test_document_record_round_trips_and_is_scoped_to_knowledge_base(tmp_path):
    store = LocalStateStore(tmp_path)
    config = ChunkingConfig(strategy_id="custom", delimiter="\n", max_length=800)
    record = DocumentRecord.new("kb-a", "notes.md", "abc123", config)

    store.save_document(record)

    assert store.list_documents("kb-a") == [record]
    assert store.list_documents("kb-b") == []
    assert store.get_document(record.id).config.strategy_id == "custom"


def test_deleting_knowledge_base_records_removes_documents_and_sessions(tmp_path):
    store = LocalStateStore(tmp_path)
    knowledge_base = store.create_knowledge_base("待删除")
    record = DocumentRecord.new(knowledge_base.id, "notes.md", "hash", ChunkingConfig())
    session = ChatSession.new(knowledge_base.id, "qwen-1.5b")
    store.save_document(record)
    store.save_session(session, [])

    store.delete_documents_for_knowledge_base(knowledge_base.id)
    store.delete_sessions_for_knowledge_base(knowledge_base.id)

    assert store.list_documents(knowledge_base.id) == []
    assert store.list_sessions() == []


def test_deleting_knowledge_base_records_removes_multi_knowledge_base_sessions(tmp_path):
    store = LocalStateStore(tmp_path)
    first = store.create_knowledge_base("第一库")
    second = store.create_knowledge_base("第二库")
    session = ChatSession.new(first.id, "qwen-1.5b")
    session.set_knowledge_base_ids([first.id, second.id])
    store.save_session(session, [])

    store.delete_sessions_for_knowledge_base(second.id)

    assert store.list_sessions() == []


def test_last_used_chunking_config_round_trips(tmp_path):
    store = LocalStateStore(tmp_path)
    config = ChunkingConfig(strategy_id="hierarchical", max_length=600, overlap_percent=15)

    store.save_chunking_default(config)

    assert store.load_chunking_default() == config


def test_recover_stale_processing_documents_marks_them_failed(tmp_path):
    store = LocalStateStore(tmp_path)
    record = DocumentRecord.new("kb-ai", "note.txt", "hash", ChunkingConfig())
    store.save_document(record)

    recovered = store.recover_stale_processing_documents()

    assert recovered == 1
    updated = store.get_document(record.id)
    assert updated.status == "failed"
    assert "上一次处理未完成" in (updated.error or "")


def test_mcp_server_definitions_round_trip_through_state(tmp_path):
    store = LocalStateStore(tmp_path)
    server = MCPServerDefinition.new(
        "本地测试服务",
        "python",
        ("-m", "tests.mcp_test_server"),
        cwd="C:/tools",
        env={"DEMO_KEY": "demo"},
    )

    store.save_mcp_server(server)

    assert LocalStateStore(tmp_path).list_mcp_servers() == [server]


def test_deleting_mcp_server_removes_only_requested_configuration(tmp_path):
    store = LocalStateStore(tmp_path)
    kept = MCPServerDefinition.new("保留", "python")
    removed = MCPServerDefinition.new("删除", "node")
    store.save_mcp_server(kept)
    store.save_mcp_server(removed)

    store.delete_mcp_server(removed.id)

    assert [item.id for item in store.list_mcp_servers()] == [kept.id]
