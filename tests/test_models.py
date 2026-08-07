from pathlib import Path

from app.config import AppConfig
from app.models import ChatSession, KnowledgeBase


def test_chat_session_has_knowledge_base_and_model():
    session = ChatSession.new("kb-ai", "qwen-1.5b")

    assert session.knowledge_base_id == "kb-ai"
    assert session.selected_knowledge_base_ids() == ["kb-ai"]
    assert session.model_id == "qwen-1.5b"
    assert session.title == "新对话"


def test_chat_session_round_trips_multiple_knowledge_bases():
    session = ChatSession.new("kb-one", "qwen-1.5b")
    session.set_knowledge_base_ids(["kb-two", "kb-one", "kb-two"])

    restored = ChatSession.from_dict(session.to_dict())

    assert restored.selected_knowledge_base_ids() == ["kb-two", "kb-one"]
    assert restored.knowledge_base_id == "kb-two"


def test_chat_session_reads_legacy_single_knowledge_base_json():
    restored = ChatSession.from_dict(
        {
            "id": "session-old",
            "title": "旧会话",
            "knowledge_base_id": "kb-old",
            "model_id": "qwen-1.5b",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )

    assert restored.selected_knowledge_base_ids() == ["kb-old"]


def test_knowledge_base_new_has_stable_identity_fields():
    knowledge_base = KnowledgeBase.new("人工智能学习", "Embedding 和 RAG 笔记")

    assert knowledge_base.id.startswith("kb-")
    assert knowledge_base.name == "人工智能学习"
    assert knowledge_base.description == "Embedding 和 RAG 笔记"
    assert knowledge_base.created_at


def test_app_config_uses_project_root_for_local_data():
    config = AppConfig.from_root(Path("G:/trial_project/004"))

    assert config.data_dir == Path("G:/trial_project/004/data")
    assert config.documents_dir == Path("G:/trial_project/004/data/documents")
    assert config.chroma_dir == Path("G:/trial_project/004/data/chroma_db")
    assert config.models_dir == Path("G:/trial_project/004/data/models")
