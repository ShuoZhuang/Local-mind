from pathlib import Path

from app.config import AppConfig
from app.models import ChatSession, KnowledgeBase


def test_chat_session_has_knowledge_base_and_model():
    session = ChatSession.new("kb-ai", "qwen-1.5b")

    assert session.knowledge_base_id == "kb-ai"
    assert session.model_id == "qwen-1.5b"
    assert session.title == "新对话"


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
