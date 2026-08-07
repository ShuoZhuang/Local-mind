from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFrame,
    QLabel,
    QListWidget,
    QPushButton,
    QMenu,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QFrame):
    knowledge_base_selected = Signal(str)
    model_selected = Signal(str)
    new_session_requested = Signal()
    knowledge_page_requested = Signal()
    chat_page_requested = Signal()
    new_knowledge_base_requested = Signal()
    session_selected = Signal(str)
    rename_knowledge_base_requested = Signal(str)
    delete_knowledge_base_requested = Signal(str)
    rename_session_requested = Signal(str)
    delete_session_requested = Signal(str)
    preheat_changed = Signal(bool)

    def __init__(self, state, model_registry, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.state = state
        self.model_registry = model_registry
        self.active_context_id: str | None = None
        self.model_combo = QComboBox()
        self.preheat_checkbox = QCheckBox("启动时预热模型")
        self.preheat_checkbox.setChecked(self.state.load_preheat_models())
        self.knowledge_base_list = QListWidget()
        self.session_list = QListWidget()
        self.new_session_button = QPushButton("＋ 新建对话")
        self.new_knowledge_base_button = QPushButton("＋ 新建知识库")
        self.knowledge_button = QPushButton("▣ 知识库管理")
        self.chat_button = QPushButton("◌ 对话")
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("✦  LocalMind\n     你的本地知识助手")
        brand.setStyleSheet("font-size: 15px; font-weight: 700; line-height: 1.5;")
        layout.addWidget(brand)
        layout.addSpacing(18)
        layout.addWidget(QLabel("当前模型"))
        layout.addWidget(self.model_combo)
        layout.addWidget(self.preheat_checkbox)
        layout.addSpacing(10)
        layout.addWidget(self.chat_button)
        layout.addWidget(self.knowledge_button)
        layout.addWidget(self.new_session_button)
        layout.addWidget(self.new_knowledge_base_button)
        layout.addWidget(QLabel("我的知识库"))
        layout.addWidget(self.knowledge_base_list)
        layout.addWidget(QLabel("最近对话"))
        layout.addWidget(self.session_list)
        status = QLabel("● 本地服务\n文档和对话只保存在本机")
        status.setObjectName("Muted")
        layout.addWidget(status)
        self.model_combo.currentIndexChanged.connect(self._emit_model)
        self.preheat_checkbox.toggled.connect(self.preheat_changed)
        self.knowledge_base_list.currentRowChanged.connect(self._emit_knowledge_base)
        self.session_list.currentRowChanged.connect(self._emit_session)
        self.knowledge_base_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.session_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.knowledge_base_list.customContextMenuRequested.connect(self._show_knowledge_base_menu)
        self.session_list.customContextMenuRequested.connect(self._show_session_menu)
        self.new_session_button.clicked.connect(self.new_session_requested)
        self.knowledge_button.clicked.connect(self.knowledge_page_requested)
        self.chat_button.clicked.connect(self.chat_page_requested)
        self.new_knowledge_base_button.clicked.connect(self.new_knowledge_base_requested)

    def refresh(self):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in self.model_registry.list_models():
            self.model_combo.addItem(model.display_name, model.id)
        self.model_combo.blockSignals(False)

        self.knowledge_base_list.blockSignals(True)
        self.knowledge_base_list.clear()
        for knowledge_base in self.state.list_knowledge_bases():
            item = self.knowledge_base_list.addItem(knowledge_base.name)
            self.knowledge_base_list.item(self.knowledge_base_list.count() - 1).setData(256, knowledge_base.id)
        self.knowledge_base_list.setCurrentRow(-1)
        self.knowledge_base_list.blockSignals(False)

        self.session_list.blockSignals(True)
        self.session_list.clear()
        for session in self.state.list_sessions():
            item = self.session_list.addItem(session.title)
            self.session_list.item(self.session_list.count() - 1).setData(256, session.id)
        self.session_list.setCurrentRow(-1)
        self.session_list.blockSignals(False)

    def activate_chat_context(self, session_id: str | None = None) -> None:
        self.active_context_id = session_id
        self.knowledge_base_list.blockSignals(True)
        self.knowledge_base_list.setCurrentRow(-1)
        self.knowledge_base_list.blockSignals(False)
        if session_id:
            self.select_session(session_id)
        else:
            self.session_list.blockSignals(True)
            self.session_list.setCurrentRow(-1)
            self.session_list.blockSignals(False)

    def activate_knowledge_context(self, knowledge_base_id: str) -> None:
        self.active_context_id = knowledge_base_id
        self.session_list.blockSignals(True)
        self.session_list.setCurrentRow(-1)
        self.session_list.blockSignals(False)
        self.knowledge_base_list.blockSignals(True)
        for row in range(self.knowledge_base_list.count()):
            if self.knowledge_base_list.item(row).data(256) == knowledge_base_id:
                self.knowledge_base_list.setCurrentRow(row)
                break
        self.knowledge_base_list.blockSignals(False)

    def _emit_model(self, index: int):
        model_id = self.model_combo.itemData(index)
        if model_id:
            self.model_selected.emit(model_id)

    def _emit_knowledge_base(self, row: int):
        if row >= 0:
            knowledge_base_id = self.knowledge_base_list.item(row).data(256)
            self.knowledge_base_selected.emit(knowledge_base_id)

    def _emit_session(self, row: int):
        if row >= 0:
            session_id = self.session_list.item(row).data(256)
            if session_id:
                self.session_selected.emit(session_id)

    def select_session(self, session_id: str) -> None:
        self.session_list.blockSignals(True)
        for row in range(self.session_list.count()):
            if self.session_list.item(row).data(256) == session_id:
                self.session_list.setCurrentRow(row)
                break
        self.session_list.blockSignals(False)

    def knowledge_base_menu(self, knowledge_base_id: str) -> QMenu:
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        rename_action.triggered.connect(
            lambda: self.rename_knowledge_base_requested.emit(knowledge_base_id)
        )
        delete_action.triggered.connect(
            lambda: self.delete_knowledge_base_requested.emit(knowledge_base_id)
        )
        return menu

    def session_menu(self, session_id: str) -> QMenu:
        menu = QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        rename_action.triggered.connect(lambda: self.rename_session_requested.emit(session_id))
        delete_action.triggered.connect(lambda: self.delete_session_requested.emit(session_id))
        return menu

    def _show_knowledge_base_menu(self, position) -> None:
        item = self.knowledge_base_list.itemAt(position)
        if item:
            self.knowledge_base_menu(item.data(256)).exec(
                self.knowledge_base_list.mapToGlobal(position)
            )

    def _show_session_menu(self, position) -> None:
        item = self.session_list.itemAt(position)
        if item:
            self.session_menu(item.data(256)).exec(self.session_list.mapToGlobal(position))
