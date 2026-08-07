import os
import inspect
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import AppConfig
from app.main import build_window
from app.models import ChatSession, ChunkingConfig, DocumentRecord
from app.services.storage import LocalStateStore
from app.ui.main_window import MainWindow
from app.ui.chat_page import ChatPage
from app.ui.context_panels import CitationPanel
from app.ui.knowledge_page import KnowledgePage
from app.ui.workers import ImportWorker


def test_main_window_contains_workspace_and_creates_session(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    knowledge_base = state.create_knowledge_base("人工智能学习", "Embedding")
    window = MainWindow(config, state, knowledge_base.id)

    assert window.sidebar.model_combo.count() >= 1
    assert window.sidebar.knowledge_base_list.count() == 1
    assert window.stack.currentWidget() is window.chat_page

    before = window.sidebar.session_list.count()
    window.sidebar.new_session_button.click()

    assert window.sidebar.session_list.count() == before + 1
    first_session_id = window.current_session.id
    window.sidebar.new_session_button.click()
    second_session_id = window.current_session.id
    first_row = next(
        row
        for row in range(window.sidebar.session_list.count())
        if window.sidebar.session_list.item(row).data(256) == first_session_id
    )
    window.sidebar.session_list.setCurrentRow(first_row)
    assert window.current_session.id == first_session_id
    assert window.current_session.id != second_session_id
    assert window.chat_page.title.text() == "新对话"
    window.close()
    application.processEvents()


def test_build_window_uses_project_local_state(tmp_path):
    application = QApplication.instance() or QApplication([])

    window = build_window(tmp_path)

    assert window.windowTitle().startswith("LocalMind")
    window.close()
    application.processEvents()


def test_selecting_a_knowledge_base_opens_its_management_page(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    first = state.create_knowledge_base("人工智能学习")
    second = state.create_knowledge_base("学生守则")
    window = MainWindow(config, state, first.id)

    window.sidebar.knowledge_base_list.setCurrentRow(1)

    assert window.current_knowledge_base_id == second.id
    assert window.stack.currentWidget() is window.knowledge_page
    assert "学生守则" in window.knowledge_page.title.text()
    window.close()
    application.processEvents()


def test_new_session_from_knowledge_page_returns_to_chat_and_selects_it(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    knowledge_base = state.create_knowledge_base("人工智能学习")
    window = MainWindow(config, state, knowledge_base.id)
    window.stack.setCurrentWidget(window.knowledge_page)

    window.sidebar.new_session_button.click()

    assert window.stack.currentWidget() is window.chat_page
    assert window.current_session is not None
    assert window.sidebar.session_list.currentItem().data(256) == window.current_session.id
    window.close()
    application.processEvents()


def test_sidebar_context_menus_offer_rename_and_delete_for_both_lists(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    knowledge_base = state.create_knowledge_base("人工智能学习")
    session = ChatSession.new(knowledge_base.id, "qwen-1.5b")
    state.save_session(session, [])
    window = MainWindow(config, state, knowledge_base.id)

    knowledge_actions = [action.text() for action in window.sidebar.knowledge_base_menu(knowledge_base.id).actions()]
    session_actions = [action.text() for action in window.sidebar.session_menu(session.id).actions()]

    assert knowledge_actions == ["重命名", "删除"]
    assert session_actions == ["重命名", "删除"]
    window.close()
    application.processEvents()


def test_deleting_last_knowledge_base_creates_a_visible_new_empty_one(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    knowledge_base = state.create_knowledge_base("待删除知识库")
    window = MainWindow(config, state, knowledge_base.id)

    monkeypatch.setattr(
        "app.ui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._delete_knowledge_base_data = lambda _knowledge_base_id: None
    window.delete_knowledge_base(knowledge_base.id)

    remaining = state.list_knowledge_bases()
    assert len(remaining) == 1
    assert remaining[0].id != knowledge_base.id
    assert remaining[0].name != knowledge_base.name
    assert window.sidebar.knowledge_base_list.item(0).text() == remaining[0].name
    window.close()
    application.processEvents()


def test_chat_page_ctrl_enter_emits_query_and_enter_keeps_newline():
    application = QApplication.instance() or QApplication([])
    page = ChatPage()
    page.show()
    spy = QSignalSpy(page.send_requested)

    page.input.setPlainText("你好")
    QTest.keyClick(page.input, Qt.Key_Return)

    assert spy.count() == 1
    assert spy.at(0)[0] == "你好"

    page.input.setPlainText("第一行")
    QTest.keyClick(page.input, Qt.Key_Return, Qt.ControlModifier)
    assert "\n" in page.input.toPlainText()
    page.close()
    application.processEvents()


def test_chat_page_renders_user_and_assistant_messages_as_widgets():
    application = QApplication.instance() or QApplication([])
    page = ChatPage()
    page.append_user("你好")
    page.start_assistant()
    page.append_token("欢迎")

    assert page.messages.itemWidget(page.messages.item(0)) is not None
    assert page.messages.itemWidget(page.messages.item(1)) is not None
    page.close()
    application.processEvents()


def test_chat_page_renders_tool_call_after_assistant_message():
    application = QApplication.instance() or QApplication([])
    page = ChatPage()
    page.start_assistant()
    page.append_token("计算结果如下")
    page.append_tool_call(
        {
            "name": "calculator",
            "result": {"success": True, "expression": "2+2", "result": "4"},
        }
    )

    assert page.messages.count() == 2
    tool_widget = page.messages.itemWidget(page.messages.item(1))
    assert tool_widget is not None
    assert tool_widget.objectName() == "ToolCallLabel"
    assert "2+2" in tool_widget.text()
    assert page.messages.item(1).sizeHint().height() >= 72
    assert tool_widget.styleSheet() == ""
    page.close()
    application.processEvents()


def test_warmup_explicitly_loads_embedding_and_llm(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    knowledge_base = state.create_knowledge_base("预热测试")
    window = MainWindow(config, state, knowledge_base.id)

    class FakeEmbedding:
        model = object()

    class FakeLLM:
        def __init__(self):
            self.loaded = False

        def load(self):
            self.loaded = True

    fake_llm = FakeLLM()
    monkeypatch.setattr(window, "_embedding", lambda: FakeEmbedding())
    monkeypatch.setattr(window, "_llm_factory", lambda _model_id: fake_llm)

    window._warmup_models()

    assert fake_llm.loaded is True
    window.close()
    application.processEvents()


def test_chat_page_grows_message_items_for_multiline_replies():
    application = QApplication.instance() or QApplication([])
    page = ChatPage()
    page.resize(900, 600)
    page.show()
    page.start_assistant()
    page.append_token("\n".join(["这是一行较长的回答内容。"] * 8))
    application.processEvents()

    item = page.messages.item(0)
    assert item.sizeHint().height() > 78
    assert page.messages.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.messages.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    assert page.messages.objectName() == "ChatMessages"
    assert page.messages.itemWidget(page.messages.item(0)).findChild(type(page._assistant_bubble)).testAttribute(
        Qt.WidgetAttribute.WA_StyledBackground
    )
    page.close()
    application.processEvents()


def test_citation_panel_wraps_results_without_a_horizontal_scrollbar():
    application = QApplication.instance() or QApplication([])
    panel = CitationPanel()
    panel.resize(280, 480)
    panel.show()
    panel.set_citations([
        {
            "file_name": "2025年学生手册——华东理工大学学生竞赛管理办法与附加说明.pdf",
            "score": 0.85,
            "text": "这是一段足够长的引用摘要，用来验证右侧回答依据区域能够自动换行，而不是出现水平滚动条。" * 3,
            "document_id": "doc-1",
        }
    ])
    application.processEvents()

    assert panel.source_list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert panel.source_list.itemWidget(panel.source_list.item(0)) is not None
    assert panel.source_list.item(0).sizeHint().height() > 48
    panel.close()
    application.processEvents()


def test_chat_page_exposes_multi_knowledge_base_menu_and_selection_signal():
    application = QApplication.instance() or QApplication([])
    page = ChatPage()
    page.set_knowledge_bases(
        [("kb-ai", "AI 笔记"), ("kb-rag", "RAG 笔记")],
        ["kb-ai"],
    )

    assert page.options_button.objectName() == "ChatOptionsButton"
    actions = page.options_button.menu().actions()
    assert any(action.text() == "全选" for action in actions)
    assert any(action.text() == "AI 笔记" for action in actions)
    page.close()
    application.processEvents()


def test_chat_page_source_line_emits_citation_payload():
    application = QApplication.instance() or QApplication([])
    page = ChatPage()
    citation = {"file_name": "notes.md", "document_id": "doc-1"}
    spy = QSignalSpy(page.citations_requested)

    page.append_citations([citation])
    page.messages.itemWidget(page.messages.item(0)).click()

    assert spy.count() == 1
    assert spy.at(0)[0][0]["document_id"] == "doc-1"
    page.close()
    application.processEvents()


def test_citation_panel_can_select_matching_document():
    application = QApplication.instance() or QApplication([])
    panel = CitationPanel()
    panel.set_citations([
        {"file_name": "one.md", "document_id": "doc-1"},
        {"file_name": "two.md", "document_id": "doc-2"},
    ])
    panel.select_citation("doc-2")

    assert panel.source_list.currentItem().data(32) == "doc-2"
    panel.close()
    application.processEvents()


def test_knowledge_page_exposes_auto_and_manual_split_options():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()

    assert page.split_mode_combo.itemText(0) == "自动分段与清洗"
    assert page.split_mode_combo.itemText(1) == "自定义分段"
    assert page.split_mode_combo.itemText(2) == "按层级分段"
    page.split_mode_combo.setCurrentIndex(1)
    assert page.manual_options.isVisible() or not page.manual_options.isVisible()
    assert page.delimiter_input.text() == "换行"
    assert page.max_length_input.value() == 800
    assert page.overlap_input.value() == 10

    status_id = page.add_document_status("处理中：note.txt")
    page.update_document_status(status_id, "失败：note.txt · 读取失败", state="error")
    assert page.documents.item(0).text() == "失败：note.txt · 读取失败"


def test_knowledge_page_lists_documents_and_emits_selected_document():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()
    record = DocumentRecord.new("kb-ai", "讲义.md", "hash", ChunkingConfig())
    record.status = "ready"
    record.chunk_count = 3
    page.set_documents([record])
    spy = QSignalSpy(page.document_selected)

    page.documents.setCurrentRow(0)

    card = page.documents.itemWidget(page.documents.item(0))
    assert card is not None
    assert "讲义.md" in card.file_name.text()
    assert page.documents.item(0).sizeHint().height() >= 74
    assert spy.count() == 1
    assert spy.at(0)[0] == record.id
    page.close()
    application.processEvents()


def test_knowledge_page_exposes_document_detail_actions():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()
    record = DocumentRecord.new("kb-ai", "讲义.md", "hash", ChunkingConfig())
    page.set_documents([record])
    page.documents.setCurrentRow(0)
    reprocess_spy = QSignalSpy(page.document_reprocess_requested)
    delete_spy = QSignalSpy(page.document_delete_requested)

    page.reprocess_button.click()
    page.delete_button.click()

    assert record.file_name in page.detail_title.text()
    assert reprocess_spy.at(0)[0] == record.id
    assert delete_spy.at(0)[0] == record.id
    page.close()
    application.processEvents()


def test_knowledge_page_exposes_view_chunks_action():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()
    record = DocumentRecord.new("kb-ai", "讲义.md", "hash", ChunkingConfig())
    page.set_documents([record])
    page.documents.setCurrentRow(0)
    spy = QSignalSpy(page.view_chunks_requested)

    page.view_chunks_button.click()

    assert spy.at(0)[0] == record.id
    page.close()
    application.processEvents()


def test_knowledge_page_shows_document_stats_and_filters_list():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()
    first = DocumentRecord.new("kb-ai", "讲义.md", "hash-1", ChunkingConfig())
    second = DocumentRecord.new("kb-ai", "实验报告.txt", "hash-2", ChunkingConfig())
    page.set_documents([first, second])

    page.search_input.setText("实验")

    assert "2" in page.stats_label.text()
    assert sum(not page.documents.item(row).isHidden() for row in range(page.documents.count())) == 1
    visible = [
        page.documents.itemWidget(page.documents.item(row)).file_name.text()
        for row in range(page.documents.count())
        if not page.documents.item(row).isHidden()
    ]
    assert "实验报告.txt" in visible[0]
    page.close()
    application.processEvents()


def test_custom_delimiter_presets_and_input_are_explicit():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()

    labels = [page.delimiter_combo.itemText(index) for index in range(page.delimiter_combo.count())]
    assert labels == [
        "换行", "两个换行", "中文句号", "中文逗号", "英文句号", "英文逗号",
        "中文问号", "英文问号", "自定义",
    ]
    assert page.custom_delimiter_input.isHidden()
    page.delimiter_combo.setCurrentIndex(8)
    assert not page.custom_delimiter_input.isHidden()
    page.custom_delimiter_input.setText("###")
    assert page.chunking_config().delimiter == "###"
    page.close()
    application.processEvents()


def test_adding_content_requires_confirmation_before_import_signal():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()
    page._pending_path = Path("note.md")
    spy = QSignalSpy(page.file_import_requested)

    page._open_import_panel()

    assert not page.import_panel.isHidden()
    assert spy.count() == 0
    page.confirm_import_button.click()
    assert spy.count() == 1
    assert spy.at(0)[0] == Path("note.md")
    page.close()
    application.processEvents()


def test_knowledge_page_selects_multiple_documents(monkeypatch):
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()
    selected = [Path("notes-a.docx"), Path("notes-b.pdf")]
    monkeypatch.setattr(
        "app.ui.knowledge_page.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(path) for path in selected], ""),
    )
    spy = QSignalSpy(page.file_selected)

    page._choose_file()

    assert spy.count() == 1
    assert spy.at(0)[0] == selected
    page.close()
    application.processEvents()


def test_main_window_exposes_import_progress_overlay(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    kb = state.create_knowledge_base("测试知识库")
    window = MainWindow(config, state, kb.id)

    window._show_import_progress("讲义.md")
    assert window.import_progress is not None
    assert window.import_progress.labelText() == "正在处理：讲义.md"
    window._close_import_progress()
    assert window.import_progress is None
    window.close()
    application.processEvents()


def test_document_detail_has_readonly_preview_area():
    application = QApplication.instance() or QApplication([])
    page = KnowledgePage()
    assert page.preview_text.isReadOnly()
    assert page.preview_text.placeholderText()
    page.close()
    application.processEvents()


def test_import_worker_is_retained_while_background_task_starts(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    kb = state.create_knowledge_base("测试知识库")
    window = MainWindow(config, state, kb.id)
    worker = ImportWorker(lambda _progress: SimpleNamespace())

    window._retain_worker(worker)

    assert worker in window._workers
    window.close()
    application.processEvents()


def test_import_worker_dispatches_ui_updates_through_main_window_slots():
    source = inspect.getsource(MainWindow._start_import_worker)

    assert "self._on_import_worker_progress" in source
    assert "self._on_import_worker_finished" in source
    assert "self._on_import_worker_failed" in source
    assert "lambda value: self._handle_import_progress" not in source


def test_sidebar_highlight_follows_active_context(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    knowledge_base = state.create_knowledge_base("人工智能学习")
    session = ChatSession.new(knowledge_base.id, "qwen-1.5b")
    state.save_session(session, [])
    window = MainWindow(config, state, knowledge_base.id)

    window.sidebar.activate_chat_context(session.id)
    assert window.sidebar.active_context_id == session.id
    assert window.sidebar.knowledge_base_list.currentRow() == -1
    assert window.sidebar.session_list.currentItem().data(256) == session.id

    window.sidebar.activate_knowledge_context(knowledge_base.id)
    assert window.sidebar.active_context_id == knowledge_base.id
    assert window.sidebar.knowledge_base_list.currentItem().data(256) == knowledge_base.id
    assert window.sidebar.session_list.currentRow() == -1
    window.sidebar.chat_button.click()
    assert window.sidebar.knowledge_base_list.currentRow() == -1
    window.sidebar.knowledge_button.click()
    assert window.sidebar.knowledge_base_list.currentItem().data(256) == knowledge_base.id
    window.close()
    application.processEvents()
