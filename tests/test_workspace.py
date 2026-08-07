import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QSignalSpy

from app.ui.workspace import WorkspaceShell
from app.ui.context_panels import CitationPanel
from app.ui.context_panels import KnowledgeImportPanel
from app.ui.context_panels import ImportProgressPanel
from app.models import ChunkingConfig, DocumentChunk, DocumentRecord
from app.ui.context_panels import DocumentDetailPanel


def test_workspace_switches_context_visibility():
    application = QApplication.instance() or QApplication([])
    shell = WorkspaceShell(QWidget(), QWidget(), QWidget())

    assert shell.context_is_visible is True
    shell.set_context_visible(False, animate=False)
    assert shell.context_is_visible is False
    assert shell.context_container.isHidden()
    assert not shell.context_expand_button.isHidden()
    shell.context_expand_button.click()
    assert shell.context_is_visible is True
    assert shell.context_expand_button.isHidden()
    shell.close()
    application.processEvents()


def test_workspace_keeps_context_rail_width_stable():
    application = QApplication.instance() or QApplication([])
    shell = WorkspaceShell(QWidget(), QWidget(), QWidget())
    shell.resize(1180, 760)
    shell.show()
    application.processEvents()

    assert 320 <= shell.context_container.minimumWidth() <= 360
    assert shell.context_container.maximumWidth() <= 360
    assert 320 <= shell.splitter.sizes()[2] <= 360
    shell.close()
    application.processEvents()


def test_workspace_auto_collapses_context_on_narrow_width():
    application = QApplication.instance() or QApplication([])
    shell = WorkspaceShell(QWidget(), QWidget(), QWidget())
    shell.resize(900, 700)
    shell.show()
    application.processEvents()

    assert shell.context_is_visible is False
    shell.resize(1300, 700)
    application.processEvents()
    assert shell.context_is_visible is True
    shell.close()
    application.processEvents()


def test_citation_panel_shows_actual_sources():
    application = QApplication.instance() or QApplication([])
    panel = CitationPanel()
    panel.set_citations([{"file_name": "学生守则.docx", "score": 0.81, "text": "第一条"}])

    card = panel.source_list.itemWidget(panel.source_list.item(0))
    assert card is not None
    assert "学生守则.docx" in card.title.text()
    assert "0.81" in card.score.text()
    panel.close()
    application.processEvents()


def test_import_panel_requires_confirmation_and_exposes_custom_delimiter():
    application = QApplication.instance() or QApplication([])
    panel = KnowledgeImportPanel()
    panel.set_pending_path(Path("notes.docx"))
    panel.strategy_combo.setCurrentText("自定义分段")
    panel.delimiter_combo.setCurrentText("自定义")

    assert not panel.custom_delimiter_input.isHidden()
    spy = QSignalSpy(panel.confirmed)
    panel.confirm_button.click()
    assert spy.count() == 1
    assert spy.at(0)[0] == Path("notes.docx")
    panel.close()
    application.processEvents()


def test_import_panel_accepts_multiple_documents_with_one_configuration():
    application = QApplication.instance() or QApplication([])
    panel = KnowledgeImportPanel()
    paths = [Path("notes-a.docx"), Path("notes-b.pdf"), Path("notes-c.md")]
    panel.set_pending_paths(paths)
    spy = QSignalSpy(panel.confirmed)

    panel.confirm_button.click()

    assert spy.count() == 1
    assert spy.at(0)[0] == paths
    assert "3" in panel.file_label.text()
    panel.close()
    application.processEvents()


def test_import_progress_panel_renders_stage():
    application = QApplication.instance() or QApplication([])
    panel = ImportProgressPanel()
    panel.set_stage("生成向量", 60, "正在准备本地模型")

    assert panel.stage_label.text() == "生成向量"
    assert panel.progress_bar.value() == 60
    assert panel.detail_label.text() == "正在准备本地模型"
    panel.close()
    application.processEvents()


def test_document_detail_panel_exposes_original_and_chunk_previews():
    application = QApplication.instance() or QApplication([])
    record = DocumentRecord.new("kb-1", "讲义.docx", "hash", ChunkingConfig())
    record.chunk_count = 2
    panel = DocumentDetailPanel()
    panel.set_document(record, [DocumentChunk("chunk-1", "第一段内容"), DocumentChunk("chunk-2", "第二段内容")])

    assert panel.preview_tabs.count() == 2
    assert "第一段内容" in panel.chunk_list.item(0).text()
    panel.close()
    application.processEvents()
