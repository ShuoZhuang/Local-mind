from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.models import MCPToolDisplayMetadata, ToolDefinition
from app.services.storage import LocalStateStore


class MCPToolDisplayDialog(QDialog):
    """Edit LocalMind's presentation text without changing the MCP Server."""

    def __init__(self, state: LocalStateStore, tool: ToolDefinition, parent=None):
        super().__init__(parent)
        self.state = state
        self.tool = tool
        self.server_id, self.tool_name = self._parse_tool_id(tool.id)
        self.setWindowTitle("编辑工具显示信息")
        self.resize(520, 380)

        layout = QVBoxLayout(self)
        hint = QLabel("这里的文字只影响 LocalMind 界面，不会修改 MCP Server，也不会影响参数 schema。留空即可恢复为工具原始说明。")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.original_name_label = QLabel(tool.raw_name or tool.name)
        self.original_name_label.setWordWrap(True)
        self.original_description_label = QLabel(tool.raw_description or tool.description)
        self.original_description_label.setObjectName("Muted")
        self.original_description_label.setWordWrap(True)
        self.display_name_input = QLineEdit()
        self.description_input = QPlainTextEdit()
        self.description_input.setFixedHeight(110)
        form.addRow("原始名称", self.original_name_label)
        form.addRow("原始简介", self.original_description_label)
        form.addRow("显示名称", self.display_name_input)
        form.addRow("显示简介", self.description_input)
        layout.addLayout(form)

        current = self.state.get_mcp_tool_display_metadata(self.server_id, self.tool_name)
        if current is not None:
            self.display_name_input.setText(current.display_name)
            self.description_input.setPlainText(current.description)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_metadata)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _parse_tool_id(tool_id: str) -> tuple[str, str]:
        prefix, server_id, tool_name = tool_id.split(":", 2)
        if prefix != "mcp" or not server_id or not tool_name:
            raise ValueError("只能编辑 MCP 工具的显示信息")
        return server_id, tool_name

    def save_metadata(self) -> None:
        self.state.save_mcp_tool_display_metadata(
            MCPToolDisplayMetadata(
                server_id=self.server_id,
                tool_name=self.tool_name,
                display_name=self.display_name_input.text().strip(),
                description=self.description_input.toPlainText().strip(),
            )
        )
        self.accept()
