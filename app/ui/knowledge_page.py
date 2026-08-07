from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models import ChunkingConfig, DocumentRecord
from app.services.documents import SplitOptions


class DocumentListCard(QFrame):
    def __init__(self, record: DocumentRecord, parent=None):
        super().__init__(parent)
        self.setObjectName("DocumentListCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(76)
        status_text = {"ready": "已就绪", "processing": "处理中", "failed": "处理失败"}[record.status]
        self.file_name = QLabel(record.file_name)
        self.file_name.setStyleSheet("font-weight: 700;")
        self.file_name.setWordWrap(False)
        self.status = QLabel(status_text)
        self.status.setObjectName("Muted")
        self.meta = QLabel(f"{record.chunk_count} 个分块  ·  {record.config.strategy_id}")
        self.meta.setObjectName("Muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)
        layout.addWidget(self.file_name)
        layout.addWidget(self.meta)
        layout.addWidget(self.status)


class KnowledgePage(QWidget):
    file_import_requested = Signal(Path, object)
    file_selected = Signal(object)
    document_selected = Signal(str)
    document_reprocess_requested = Signal(str)
    document_delete_requested = Signal(str)
    view_chunks_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background: #141923; color: #edf2f7; font-family: 'Microsoft YaHei'; }"
            "QLabel { background: transparent; }"
            "QGroupBox { border: 1px solid #2b3749; border-radius: 14px; margin-top: 12px; padding: 16px; background: #171e29; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #edf2f7; font-weight: 700; }"
            "QLineEdit, QComboBox, QSpinBox, QTextEdit { border: 1px solid #354258; border-radius: 10px; padding: 9px; background: #1a222e; color: #e6edf5; }"
            "QPushButton { border: 1px solid #344055; border-radius: 10px; padding: 9px 14px; background: #1a222e; color: #c8d2df; }"
            "QPushButton:hover { border-color: #82e6c5; color: #e4fff8; }"
            "QListWidget { border: 1px solid #2b3749; border-radius: 14px; padding: 8px; background: #171e29; }"
            "QListWidget::item { padding: 0; margin: 0; border: 0; background: transparent; }"
            "QListWidget::item:selected { background: transparent; }"
        )
        self.title = QLabel("知识库管理")
        self.summary = QLabel("选择一个知识库后，在这里添加和管理文档。")
        self.stats_label = QLabel("文档 0 · 片段 0")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索文档名称…")
        self.documents = QListWidget()
        self.documents.setObjectName("DocumentList")
        self.documents.setSpacing(8)
        self.documents.setStyleSheet(
            "QListWidget#DocumentList::item { background: transparent; padding: 0; margin: 4px 0; }"
            "QListWidget#DocumentList::item:hover, QListWidget#DocumentList::item:selected { background: transparent; }"
        )
        self.add_button = QPushButton("＋ 添加文档")
        self.split_mode_combo = QComboBox()
        self.split_mode_combo.addItems(["自动分段与清洗", "自定义分段", "按层级分段"])
        self.manual_options = QGroupBox("手动分割设置")
        self.delimiter_input = QLineEdit("换行")
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([
            "换行", "两个换行", "中文句号", "中文逗号", "英文句号", "英文逗号",
            "中文问号", "英文问号", "自定义",
        ])
        self.custom_delimiter_input = QLineEdit("###")
        self.custom_delimiter_input.setPlaceholderText("请输入自定义分隔符")
        self.max_length_input = QSpinBox()
        self.max_length_input.setRange(1, 1000000)
        self.max_length_input.setValue(800)
        self.overlap_input = QSpinBox()
        self.overlap_input.setRange(0, 99)
        self.overlap_input.setValue(10)
        self.normalize_whitespace = QCheckBox("替换掉连续的空格、换行符和制表符")
        self.normalize_whitespace.setChecked(True)
        self.remove_urls_emails = QCheckBox("删除所有 URL 和电子邮箱地址")
        self._document_items: dict[str, QListWidgetItem] = {}
        self._records: dict[str, DocumentRecord] = {}
        self.detail_panel = QGroupBox("文档详情")
        self.detail_title = QLabel("选择一个文档查看详情")
        self.detail_summary = QLabel("")
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("文档预览将在这里显示")
        self.reprocess_button = QPushButton("重新处理")
        self.delete_button = QPushButton("删除文档")
        self.view_chunks_button = QPushButton("查看全部片段")
        self.import_panel = QGroupBox("添加内容")
        self.import_file_label = QLabel("尚未选择文件")
        self.confirm_import_button = QPushButton("确认并开始处理")
        self.cancel_import_button = QPushButton("取消")
        self._pending_path: Path | None = None
        self._pending_paths: list[Path] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.addWidget(self.title)
        layout.addWidget(self.summary)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.search_input)
        manual_layout = QFormLayout(self.manual_options)
        manual_layout.addRow("分段标识符", self.delimiter_combo)
        manual_layout.addRow("自定义分隔符", self.custom_delimiter_input)
        manual_layout.addRow("分段最大长度", self.max_length_input)
        manual_layout.addRow("分段重叠度 %", self.overlap_input)
        manual_layout.addRow(self.normalize_whitespace)
        manual_layout.addRow(self.remove_urls_emails)
        layout.addWidget(self.add_button)
        import_layout = QVBoxLayout(self.import_panel)
        import_layout.addWidget(self.import_file_label)
        import_layout.addWidget(QLabel("文档分割方式"))
        import_layout.addWidget(self.split_mode_combo)
        import_layout.addWidget(self.manual_options)
        actions = QHBoxLayout()
        actions.addWidget(self.cancel_import_button)
        actions.addWidget(self.confirm_import_button)
        import_layout.addLayout(actions)
        self.custom_delimiter_input.setHidden(True)
        self.import_panel.setHidden(True)
        layout.addWidget(self.import_panel)
        body = QHBoxLayout()
        body.addWidget(self.documents, 3)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_summary)
        detail_layout.addWidget(self.preview_text, 1)
        detail_layout.addWidget(self.view_chunks_button)
        detail_layout.addWidget(self.reprocess_button)
        detail_layout.addWidget(self.delete_button)
        detail_layout.addStretch(1)
        body.addWidget(self.detail_panel, 2)
        layout.addLayout(body, 1)
        # Document detail is now rendered by the shared right-side context rail.
        self.detail_panel.setHidden(True)
        self.add_button.clicked.connect(self._choose_file)
        self.cancel_import_button.clicked.connect(self._close_import_panel)
        self.confirm_import_button.clicked.connect(self._confirm_import)
        self.documents.currentItemChanged.connect(self._emit_document_selected)
        self.search_input.textChanged.connect(self._filter_documents)
        self.reprocess_button.clicked.connect(self._request_reprocess)
        self.delete_button.clicked.connect(self._request_delete)
        self.view_chunks_button.clicked.connect(self._request_view_chunks)
        self.split_mode_combo.currentIndexChanged.connect(
            lambda index: self.manual_options.setVisible(index == 1)
        )
        self.delimiter_combo.currentIndexChanged.connect(
            lambda index: self.custom_delimiter_input.setHidden(index != 8)
        )

    def set_knowledge_base(self, name: str):
        self.title.setText(f"知识库管理 · {name}")

    def add_document_status(self, text: str, status_id: str | None = None) -> str:
        status_id = status_id or uuid4().hex
        item = QListWidgetItem(text)
        item.setData(32, status_id)
        self.documents.addItem(item)
        self._document_items[status_id] = item
        return status_id

    def update_document_status(self, status_id: str, text: str, state: str = "processing"):
        item = self._document_items.get(status_id)
        if item is None:
            return
        item.setText(text)
        item.setData(33, state)

    def clear_documents(self):
        self.documents.clear()
        self._document_items.clear()
        self._records.clear()

    def set_documents(self, records: list[DocumentRecord]):
        self.clear_documents()
        self._all_records = list(records)
        self.stats_label.setText(
            f"文档 {len(records)} · 片段 {sum(record.chunk_count for record in records)}"
        )
        for record in records:
            self._records[record.id] = record
            status = {
                "ready": "已就绪",
                "processing": "处理中",
                "failed": "失败",
            }[record.status]
            item = QListWidgetItem()
            item.setData(32, record.id)
            item.setData(33, record.status)
            self.documents.addItem(item)
            card = DocumentListCard(record)
            item.setSizeHint(QSize(0, 80))
            self.documents.setItemWidget(item, card)
            self._document_items[record.id] = item

    def _filter_documents(self, query: str):
        query = query.strip().lower()
        for record_id, item in self._document_items.items():
            record = self._records.get(record_id)
            item.setHidden(bool(query and record and query not in record.file_name.lower()))

    def _emit_document_selected(self, item, _previous):
        if item is not None:
            document_id = item.data(32)
            if document_id:
                record = self._records.get(str(document_id))
                if record:
                    self.detail_title.setText(record.file_name)
                    self.detail_summary.setText(
                        f"状态：{record.status}\n片段：{record.chunk_count}\n"
                        f"策略：{record.config.strategy_id}\n来源：{record.source_path or '尚未保存'}"
                    )
                self.document_selected.emit(str(document_id))

    def _current_document_id(self) -> str | None:
        item = self.documents.currentItem()
        return str(item.data(32)) if item is not None and item.data(32) else None

    def _request_reprocess(self):
        document_id = self._current_document_id()
        if document_id:
            self.document_reprocess_requested.emit(document_id)

    def _request_delete(self):
        document_id = self._current_document_id()
        if document_id:
            self.document_delete_requested.emit(document_id)

    def _request_view_chunks(self):
        document_id = self._current_document_id()
        if document_id:
            self.view_chunks_requested.emit(document_id)

    def split_options(self) -> SplitOptions:
        if self.split_mode_combo.currentIndex() == 0:
            return SplitOptions(mode="auto")
        delimiter = self.delimiter_input.text()
        if delimiter == "换行":
            delimiter = "\n"
        return SplitOptions(
            mode="manual",
            delimiter=delimiter,
            max_length=self.max_length_input.value(),
            overlap_percent=self.overlap_input.value(),
            normalize_whitespace=self.normalize_whitespace.isChecked(),
            remove_urls_emails=self.remove_urls_emails.isChecked(),
        )

    def chunking_config(self) -> ChunkingConfig:
        strategy_id = ("auto", "custom", "hierarchical")[self.split_mode_combo.currentIndex()]
        delimiters = ["\n", "\n\n", "。", "，", ".", ",", "？", "?", self.custom_delimiter_input.text()]
        delimiter = delimiters[self.delimiter_combo.currentIndex()]
        return ChunkingConfig(
            strategy_id=strategy_id,
            delimiter=delimiter,
            max_length=self.max_length_input.value(),
            overlap_percent=self.overlap_input.value(),
            normalize_whitespace=self.normalize_whitespace.isChecked(),
            remove_urls_emails=self.remove_urls_emails.isChecked(),
        )

    def set_chunking_config(self, config: ChunkingConfig):
        self.split_mode_combo.setCurrentIndex({"auto": 0, "custom": 1, "hierarchical": 2}[config.strategy_id])
        presets = {"\n": 0, "\n\n": 1, "。": 2, "，": 3, ".": 4, ",": 5, "？": 6, "?": 7}
        if config.delimiter in presets:
            self.delimiter_combo.setCurrentIndex(presets[config.delimiter])
        else:
            self.delimiter_combo.setCurrentIndex(8)
            self.custom_delimiter_input.setText(config.delimiter)
        self.max_length_input.setValue(config.max_length)
        self.overlap_input.setValue(config.overlap_percent)
        self.normalize_whitespace.setChecked(config.normalize_whitespace)
        self.remove_urls_emails.setChecked(config.remove_urls_emails)

    def _choose_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文档",
            "",
            "Documents (*.txt *.md *.markdown *.pdf *.docx)",
        )
        if paths:
            self._pending_paths = [Path(path) for path in paths]
            self._pending_path = self._pending_paths[0]
            self.file_selected.emit(self._pending_paths if len(self._pending_paths) > 1 else self._pending_path)

    def _open_import_panel(self):
        self.import_file_label.setText(
            f"待导入：{self._pending_path.name}" if self._pending_path else "请选择一个文档"
        )
        self.import_panel.setHidden(False)

    def _close_import_panel(self):
        self.import_panel.setHidden(True)
        self._pending_path = None

    def _confirm_import(self):
        if self._pending_path is None:
            return
        path = self._pending_path
        config = self.chunking_config()
        self._close_import_panel()
        self.file_import_requested.emit(path, config)

    def _open_import_panel(self):
        paths = self._pending_paths or ([self._pending_path] if self._pending_path else [])
        if len(paths) == 1:
            self.import_file_label.setText(f"待导入：{paths[0].name}")
        elif paths:
            self.import_file_label.setText(f"待导入 {len(paths)} 个文档：{'、'.join(path.name for path in paths)}")
        else:
            self.import_file_label.setText("请选择一个文档")
        self.import_panel.setHidden(False)

    def _close_import_panel(self):
        self.import_panel.setHidden(True)
        self._pending_path = None
        self._pending_paths = []

    def _confirm_import(self):
        paths = self._pending_paths or ([self._pending_path] if self._pending_path else [])
        if not paths:
            return
        config = self.chunking_config()
        self._close_import_panel()
        for path in paths:
            self.file_import_requested.emit(path, config)
