from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QProgressBar, QSpinBox, QStackedWidget, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget, QMenu,
)

from app.models import ChunkingConfig, DocumentChunk, DocumentRecord


class CitationCard(QFrame):
    """A width-aware citation row so narrow context rails wrap instead of scrolling sideways."""

    def __init__(self, index: int, citation: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("CitationCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        score = citation.get("score")
        score_text = f"相似度 {score:.2f}" if isinstance(score, (int, float)) else ""

        knowledge_base_name = str(citation.get("knowledge_base_name") or "").strip()
        source_name = str(citation.get("file_name", "未知来源"))
        title = f"{index}. {knowledge_base_name} · {source_name}" if knowledge_base_name else f"{index}. {source_name}"
        self.title = QLabel(title)
        self.title.setObjectName("CitationTitle")
        self.title.setWordWrap(True)
        self.score = QLabel(score_text)
        self.score.setObjectName("Muted")
        self.preview = QLabel(str(citation.get("text", "")).strip())
        self.preview.setObjectName("CitationPreview")
        self.preview.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(4)
        layout.addWidget(self.title)
        if score_text:
            layout.addWidget(self.score)
        layout.addWidget(self.preview)


class CitationPanel(QWidget):
    document_requested = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title = QLabel("回答依据")
        self.title.setObjectName("Title")
        self.hint = QLabel("本次回答检索到的资料会显示在这里。")
        self.hint.setObjectName("Muted")
        self.source_list = QListWidget()
        self.source_list.setObjectName("CitationList")
        self.source_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.source_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.source_list.setWordWrap(True)
        self.source_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.source_list.setStyleSheet(
            "QListWidget#CitationList::item { background: transparent; border: 0; padding: 0; margin: 4px 0; }"
            "QListWidget#CitationList::item:hover, QListWidget#CitationList::item:selected { background: transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 18)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addWidget(self.source_list, 1)
        self.source_list.itemActivated.connect(self._open_source)

    def set_empty_state(self, reason: str) -> None:
        self.source_list.clear()
        self.hint.setText(reason)

    def set_citations(self, citations: list[dict]) -> None:
        self.source_list.clear()
        if not citations:
            self.set_empty_state("未检索到相关资料")
            return
        self.hint.setText(f"已参考 {len(citations)} 段资料")
        for index, citation in enumerate(citations[:3], start=1):
            score = citation.get("score")
            legacy_text = str(citation.get("file_name", "未知来源"))
            if isinstance(score, (int, float)):
                legacy_text = f"{legacy_text}  {score:.2f}"
            item = QListWidgetItem()
            item.setData(32, citation.get("document_id"))
            card = CitationCard(index, citation)
            self.source_list.addItem(item)
            self.source_list.setItemWidget(item, card)
            self._resize_citation_item(item, card)
            QTimer.singleShot(0, lambda current_item=item, current_card=card: self._resize_citation_item(current_item, current_card))

    def select_citation(self, document_id: str | None) -> None:
        if not document_id:
            return
        for index in range(self.source_list.count()):
            card = self.source_list.itemWidget(self.source_list.item(index))
            if card is not None:
                card.setProperty("selected", False)
                card.style().unpolish(card)
                card.style().polish(card)
        for index in range(self.source_list.count()):
            item = self.source_list.item(index)
            if str(item.data(32) or "") == str(document_id):
                self.source_list.setCurrentItem(item)
                self.source_list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
                card = self.source_list.itemWidget(item)
                if card is not None:
                    card.setProperty("selected", True)
                    card.style().unpolish(card)
                    card.style().polish(card)
                break

    def _resize_citation_item(self, item: QListWidgetItem, card: CitationCard) -> None:
        available_width = max(150, self.source_list.viewport().width() - 8)
        card.setFixedWidth(available_width)
        card.layout().activate()
        card.adjustSize()
        height = max(108, card.sizeHint().height() + 12)
        card.setFixedHeight(height)
        item.setSizeHint(QSize(0, height))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._resize_citations)

    def _resize_citations(self) -> None:
        for index in range(self.source_list.count()):
            item = self.source_list.item(index)
            card = self.source_list.itemWidget(item)
            if isinstance(card, CitationCard):
                self._resize_citation_item(item, card)

    def _open_source(self, item) -> None:
        document_id = item.data(32)
        if document_id:
            self.document_requested.emit(str(document_id))


class KnowledgeOverviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title = QLabel("知识库概览")
        self.title.setObjectName("Title")
        self.summary = QLabel("选择一个文档后，可以在这里查看原文和分块。")
        self.summary.setObjectName("Muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 18)
        layout.addWidget(self.title)
        layout.addWidget(self.summary)
        layout.addStretch(1)

    def set_knowledge_base(self, name: str, document_count: int) -> None:
        self.title.setText(name)
        self.summary.setText(f"当前知识库共有 {document_count} 个文档。选择文档以查看详情。")


class KnowledgeImportPanel(QWidget):
    """Right-rail import settings. It never starts work until confirmed."""

    confirmed = Signal(object, object)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[Path] = []
        self.title = QLabel("添加文档")
        self.title.setObjectName("Title")
        self.file_label = QLabel("请选择一个文件")
        self.file_label.setObjectName("Muted")
        self.file_label.setWordWrap(True)
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["自动分段", "自定义分段", "按层级分段"])
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems(["换行", "两个换行", "中文句号", "中文逗号", "英文句号", "英文逗号", "中文问号", "英文问号", "自定义"])
        self.custom_delimiter_input = QLineEdit("###")
        self.max_length_input = QSpinBox()
        self.max_length_input.setRange(1, 1_000_000)
        self.max_length_input.setValue(800)
        self.overlap_input = QSpinBox()
        self.overlap_input.setRange(0, 99)
        self.overlap_input.setValue(10)
        self.confirm_button = QPushButton("确认开始处理")
        self.confirm_button.setObjectName("PrimaryButton")
        self.cancel_button = QPushButton("取消")
        form = QFormLayout()
        form.addRow("分段方式", self.strategy_combo)
        form.addRow("分段标识符", self.delimiter_combo)
        form.addRow("自定义标识符", self.custom_delimiter_input)
        form.addRow("最大长度", self.max_length_input)
        form.addRow("重叠比例", self.overlap_input)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 18)
        layout.addWidget(self.title)
        layout.addWidget(self.file_label)
        layout.addLayout(form)
        layout.addStretch(1)
        actions = QHBoxLayout()
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.confirm_button)
        layout.addLayout(actions)
        self.strategy_combo.currentIndexChanged.connect(self._update_fields)
        self.delimiter_combo.currentIndexChanged.connect(self._update_fields)
        self.confirm_button.clicked.connect(self._confirm)
        self.cancel_button.clicked.connect(self.cancelled)
        self._update_fields()

    def set_pending_path(self, path: Path) -> None:
        self.set_pending_paths([path])

    def set_pending_paths(self, paths: list[Path]) -> None:
        self._paths = [Path(path) for path in paths]
        if not self._paths:
            self.file_label.setText("请选择一个文件")
        elif len(self._paths) == 1:
            self.file_label.setText(f"待导入：{self._paths[0].name}")
        else:
            names = "、".join(path.name for path in self._paths)
            self.file_label.setText(f"待导入 {len(self._paths)} 个文档：{names}")
        self.confirm_button.setEnabled(True)

    def set_chunking_config(self, config: ChunkingConfig) -> None:
        self.strategy_combo.setCurrentIndex({"auto": 0, "custom": 1, "hierarchical": 2}[config.strategy_id])
        values = ["\n", "\n\n", "。", "，", ".", ",", "？", "?" ]
        if config.delimiter in values:
            self.delimiter_combo.setCurrentIndex(values.index(config.delimiter))
        else:
            self.delimiter_combo.setCurrentIndex(8)
            self.custom_delimiter_input.setText(config.delimiter)
        self.max_length_input.setValue(config.max_length)
        self.overlap_input.setValue(config.overlap_percent)

    def chunking_config(self) -> ChunkingConfig:
        delimiters = ["\n", "\n\n", "。", "，", ".", ",", "？", "?", self.custom_delimiter_input.text()]
        return ChunkingConfig(
            strategy_id=("auto", "custom", "hierarchical")[self.strategy_combo.currentIndex()],
            delimiter=delimiters[self.delimiter_combo.currentIndex()],
            max_length=self.max_length_input.value(),
            overlap_percent=self.overlap_input.value(),
        )

    def _update_fields(self) -> None:
        is_custom = self.strategy_combo.currentIndex() == 1
        self.delimiter_combo.setVisible(is_custom)
        self.custom_delimiter_input.setVisible(is_custom and self.delimiter_combo.currentIndex() == 8)

    def _confirm(self) -> None:
        if self._paths:
            selected = self._paths[0] if len(self._paths) == 1 else list(self._paths)
            self.confirmed.emit(selected, self.chunking_config())


class ImportProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title = QLabel("正在建立知识库")
        self.title.setObjectName("Title")
        self.stage_label = QLabel("准备开始")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("Muted")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.addWidget(self.title)
        layout.addWidget(self.stage_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch(1)

    def set_stage(self, stage: str, percent: int, detail: str = "") -> None:
        self.stage_label.setText(stage)
        self.detail_label.setText(detail)
        self.progress_bar.setValue(percent)


class DocumentDetailPanel(QWidget):
    reprocess_requested = Signal(str)
    delete_requested = Signal(str)
    chunk_delete_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._document_id: str | None = None
        self.title = QLabel("文档详情")
        self.title.setObjectName("Title")
        self.metadata = QLabel("选择一个文档查看来源、分段策略和内容。")
        self.metadata.setObjectName("Muted")
        self.preview_tabs = QTabWidget()
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.chunk_list = QListWidget()
        self.preview_tabs.addTab(self.preview, "原文预览")
        self.preview_tabs.addTab(self.chunk_list, "分块预览")
        self.chunk_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chunk_list.customContextMenuRequested.connect(self._show_chunk_menu)
        self.reprocess_button = QPushButton("重新处理")
        self.delete_button = QPushButton("删除文档")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 18)
        layout.addWidget(self.title)
        layout.addWidget(self.metadata)
        layout.addWidget(self.preview_tabs, 1)
        actions = QHBoxLayout()
        actions.addWidget(self.reprocess_button)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        self.reprocess_button.clicked.connect(lambda: self._document_id and self.reprocess_requested.emit(self._document_id))
        self.delete_button.clicked.connect(lambda: self._document_id and self.delete_requested.emit(self._document_id))

    def set_document(self, record: DocumentRecord, chunks: list[DocumentChunk]) -> None:
        self._document_id = record.id
        self.title.setText(record.file_name)
        self.metadata.setText(f"状态：{record.status}\n分块：{record.chunk_count}\n策略：{record.config.strategy_id}")
        self.preview.setPlainText("\n\n".join(chunk.text for chunk in chunks[:5]))
        self.chunk_list.clear()
        for index, chunk in enumerate(chunks, start=1):
            text = chunk.text.strip()
            summary = text[:150] + ("…" if len(text) > 150 else "")
            item = QListWidgetItem(f"分块 {index} · {len(text)} 字\n{summary}")
            item.setData(Qt.ItemDataRole.UserRole, chunk.id)
            self.chunk_list.addItem(item)

    def chunk_context_menu_for_row(self, row: int) -> QMenu:
        """构造分块右键菜单，便于界面事件和离屏测试复用。"""
        menu = QMenu(self)
        item = self.chunk_list.item(row)
        if item is None or not self._document_id:
            return menu
        chunk_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not chunk_id:
            return menu
        action = menu.addAction("从知识库移除")
        action.triggered.connect(
            lambda checked=False, document_id=self._document_id, identifier=chunk_id:
            self.chunk_delete_requested.emit(document_id, identifier)
        )
        return menu

    def _show_chunk_menu(self, position) -> None:
        item = self.chunk_list.itemAt(position)
        if item is None:
            return
        menu = self.chunk_context_menu_for_row(self.chunk_list.row(item))
        if menu.actions():
            menu.exec(self.chunk_list.viewport().mapToGlobal(position))
