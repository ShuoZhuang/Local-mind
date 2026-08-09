from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.models import MCPServerDefinition
from app.services.storage import LocalStateStore


class MCPServerDialog(QDialog):
    """Manage explicitly approved local stdio MCP server definitions."""

    servers_changed = Signal()

    def __init__(self, state: LocalStateStore, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_server_id: str | None = None
        self.setWindowTitle("管理 MCP Server")
        self.resize(720, 500)

        root = QHBoxLayout(self)
        self.server_list = QListWidget()
        self.server_list.setMinimumWidth(190)
        root.addWidget(self.server_list, 1)

        editor = QVBoxLayout()
        warning = QLabel("仅添加你信任的本地 MCP Server。保存后，LocalMind 才会在你手动测试时启动该命令。")
        warning.setWordWrap(True)
        warning.setObjectName("Muted")
        editor.addWidget(warning)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.command_input = QLineEdit()
        self.arguments_input = QPlainTextEdit("[]")
        self.arguments_input.setFixedHeight(72)
        self.cwd_input = QLineEdit()
        self.environment_input = QPlainTextEdit("{}")
        self.environment_input.setFixedHeight(72)
        self.enabled_checkbox = QCheckBox("启用此 Server")
        self.enabled_checkbox.setChecked(True)
        form.addRow("名称", self.name_input)
        form.addRow("命令", self.command_input)
        form.addRow("参数（JSON 数组）", self.arguments_input)
        form.addRow("工作目录（可选）", self.cwd_input)
        form.addRow("环境变量（JSON 对象）", self.environment_input)
        form.addRow("", self.enabled_checkbox)
        editor.addLayout(form)
        buttons = QHBoxLayout()
        self.new_button = QPushButton("新建")
        self.delete_button = QPushButton("删除")
        self.save_button = QPushButton("保存配置")
        self.save_button.setObjectName("PrimaryButton")
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        editor.addLayout(buttons)
        root.addLayout(editor, 3)

        self.server_list.currentRowChanged.connect(self._load_selected)
        self.new_button.clicked.connect(self.new_server)
        self.delete_button.clicked.connect(self.delete_current_server)
        self.save_button.clicked.connect(self.save_current_server)
        self.refresh()

    def refresh(self) -> None:
        selected_id = self.current_server_id
        self.server_list.clear()
        for server in self.state.list_mcp_servers():
            self.server_list.addItem(server.name)
            item = self.server_list.item(self.server_list.count() - 1)
            item.setData(32, server.id)
            if server.id == selected_id:
                self.server_list.setCurrentItem(item)
        if self.server_list.currentRow() < 0:
            self.new_server()

    def new_server(self) -> None:
        self.current_server_id = None
        self.server_list.setCurrentRow(-1)
        self.name_input.clear()
        self.command_input.clear()
        self.arguments_input.setPlainText("[]")
        self.cwd_input.clear()
        self.environment_input.setPlainText("{}")
        self.enabled_checkbox.setChecked(True)
        self.name_input.setFocus()

    def _load_selected(self, _row: int) -> None:
        item = self.server_list.currentItem()
        if item is None:
            return
        server_id = item.data(32)
        server = next((value for value in self.state.list_mcp_servers() if value.id == server_id), None)
        if server is None:
            return
        self.current_server_id = server.id
        self.name_input.setText(server.name)
        self.command_input.setText(server.command)
        self.arguments_input.setPlainText(json.dumps(server.args, ensure_ascii=False, indent=2))
        self.cwd_input.setText(server.cwd or "")
        self.environment_input.setPlainText(json.dumps(server.env, ensure_ascii=False, indent=2))
        self.enabled_checkbox.setChecked(server.enabled)

    def save_current_server(self) -> None:
        name = self.name_input.text().strip()
        command = self.command_input.text().strip()
        if not name or not command:
            QMessageBox.warning(self, "无法保存", "名称和命令不能为空。")
            return
        try:
            args = json.loads(self.arguments_input.toPlainText() or "[]")
            env = json.loads(self.environment_input.toPlainText() or "{}")
        except json.JSONDecodeError as error:
            QMessageBox.warning(self, "JSON 格式错误", str(error))
            return
        if not isinstance(args, list) or not all(isinstance(value, str) for value in args):
            QMessageBox.warning(self, "参数格式错误", "参数必须是 JSON 字符串数组。")
            return
        if not isinstance(env, dict):
            QMessageBox.warning(self, "环境变量格式错误", "环境变量必须是 JSON 对象。")
            return
        answer = QMessageBox.question(
            self,
            "确认本地命令",
            "此命令会在本机执行，请只添加可信 MCP Server。是否保存？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        existing = next(
            (value for value in self.state.list_mcp_servers() if value.id == self.current_server_id),
            None,
        )
        server = existing or MCPServerDefinition.new(name, command)
        server.name = name
        server.command = command
        server.args = list(args)
        server.cwd = self.cwd_input.text().strip() or None
        server.env = {str(key): str(value) for key, value in env.items()}
        server.enabled = self.enabled_checkbox.isChecked()
        self.state.save_mcp_server(server)
        self.current_server_id = server.id
        self.refresh()
        self.servers_changed.emit()

    def delete_current_server(self) -> None:
        if not self.current_server_id:
            self.new_server()
            return
        answer = QMessageBox.question(
            self,
            "删除 MCP Server",
            "仅删除 LocalMind 中保存的配置，不会删除外部 MCP Server 文件。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.state.delete_mcp_server(self.current_server_id)
        self.current_server_id = None
        self.refresh()
        self.servers_changed.emit()
