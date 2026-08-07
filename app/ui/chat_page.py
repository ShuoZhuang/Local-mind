from __future__ import annotations

from PySide6.QtCore import QTimer, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MessageBubble(QFrame):
    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("UserBubble" if role == "user" else "AssistantBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.role_label = QLabel("你" if role == "user" else "LocalMind")
        self.role_label.setObjectName("Muted")
        self.content_label = QLabel(text)
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(5)
        layout.addWidget(self.role_label)
        layout.addWidget(self.content_label)


class PromptEdit(QPlainTextEdit):
    send_requested = Signal()

    def keyPressEvent(self, event):
        if event.key() in {Qt.Key_Return, Qt.Key_Enter} and event.modifiers() & Qt.ControlModifier:
            self.insertPlainText("\n")
            event.accept()
            return
        if event.key() in {Qt.Key_Return, Qt.Key_Enter} and not event.modifiers():
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ChatPage(QWidget):
    send_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = QListWidget()
        self.messages.setObjectName("ChatMessages")
        self.messages.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.messages.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.messages.setStyleSheet(
            "QListWidget#ChatMessages::item { background: transparent; padding: 0; margin: 4px 0; }"
            "QListWidget#ChatMessages::item:hover, QListWidget#ChatMessages::item:selected { background: transparent; }"
        )
        self.input = PromptEdit()
        self.send_button = QPushButton("发送 ↑")
        self.send_button.setObjectName("PrimaryButton")
        self._assistant_bubble = None
        self._assistant_item = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        self.title = QLabel("今天想探索什么？")
        self.title.setObjectName("Title")
        self.subtitle = QLabel("先检索当前知识库，再由本地模型组织答案。")
        self.subtitle.setObjectName("Muted")
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.messages, 1)
        self.input.setPlaceholderText("输入问题，按 Enter 发送；Ctrl+Enter 换行……")
        self.input.setMaximumHeight(110)
        layout.addWidget(self.input)
        footer = QHBoxLayout()
        footer.addWidget(QLabel("回答由本地模型生成 · 不会上传文档"))
        footer.addStretch()
        footer.addWidget(self.send_button)
        layout.addLayout(footer)
        self.send_button.clicked.connect(self._send)
        self.input.send_requested.connect(self._send)

    def set_knowledge_base(self, name: str):
        self.subtitle.setText("回答将优先参考当前知识库中的资料。")

    def set_session_title(self, title: str):
        self.title.setText(title.strip() or "新对话")

    def append_user(self, text: str):
        self._append_bubble("user", text)

    def start_assistant(self):
        self._assistant_bubble = self._append_bubble("assistant", "")
        self._assistant_item = getattr(self._assistant_bubble, "_list_item", None)

    def append_token(self, token: str):
        if getattr(self, "_assistant_bubble", None) is not None:
            self._assistant_bubble.content_label.setText(self._assistant_bubble.content_label.text() + token)
            self._resize_message_item(self._assistant_item, self._assistant_bubble)

    def append_citations(self, citations: list[dict]):
        if citations:
            sources = "  来源：" + "、".join(str(item.get("file_name", "未知")) for item in citations)
            label = QLabel(sources)
            label.setObjectName("CitationLabel")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            item = QListWidgetItem()
            self.messages.addItem(item)
            self.messages.setItemWidget(item, label)
            self._resize_widget_item(item, label, minimum_height=32)
            QTimer.singleShot(0, lambda: self._resize_widget_item(item, label, minimum_height=32))

    def append_tool_call(self, tool_call: dict) -> None:
        result = tool_call.get("result", {}) if isinstance(tool_call, dict) else {}
        name = str(tool_call.get("name", "未知工具")) if isinstance(tool_call, dict) else "未知工具"
        success = bool(result.get("success"))
        expression = result.get("expression")
        value = result.get("result") if success else (result.get("error") or {}).get("message", "调用失败")
        detail = f"表达式：{expression}\n" if expression else ""
        label = QLabel(f"工具调用 · {name}\n{detail}结果：{value}")
        label.setObjectName("ToolCallLabel")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        item = QListWidgetItem()
        self.messages.addItem(item)
        self.messages.setItemWidget(item, label)
        self._resize_widget_item(item, label, minimum_height=72, extra_height=12)
        QTimer.singleShot(
            0,
            lambda: self._resize_widget_item(item, label, minimum_height=72, extra_height=12),
        )

    def append_error(self, message: str):
        self._append_bubble("assistant", f"错误：{message}")

    def set_generation_active(self, active: bool):
        self.send_button.setEnabled(True)
        self.input.setEnabled(not active)
        self.send_button.setText("停止生成" if active else "发送 ↑")
        try:
            self.send_button.clicked.disconnect()
        except RuntimeError:
            pass
        self.send_button.clicked.connect(self.stop_requested if active else self._send)

    def display_messages(self, messages):
        self.messages.clear()
        for message in messages:
            self._append_bubble(message.role, message.content)
            if message.citations:
                self.append_citations(message.citations)
            for tool_call in message.tool_calls:
                self.append_tool_call(tool_call)

    def _append_bubble(self, role: str, text: str) -> MessageBubble:
        item = QListWidgetItem()
        bubble = MessageBubble(role, text)
        row = QWidget()
        row.setObjectName("MessageRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 18, 0)
        row_layout.setSpacing(0)
        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)
        self.messages.addItem(item)
        self.messages.setItemWidget(item, row)
        bubble._list_item = item
        bubble._message_row = row
        self._resize_message_item(item, bubble)
        QTimer.singleShot(0, lambda: self._resize_message_item(item, bubble))
        self.messages.scrollToBottom()
        return bubble

    def _resize_widget_item(
        self,
        item: QListWidgetItem,
        widget: QWidget,
        minimum_height: int = 0,
        extra_height: int = 0,
    ):
        if item is None or widget is None:
            return
        width = max(240, self.messages.viewport().width() - 32)
        widget.setFixedWidth(width)
        widget.adjustSize()
        height = max(minimum_height, widget.sizeHint().height() + extra_height)
        item.setSizeHint(QSize(0, height))

    def _resize_message_item(self, item: QListWidgetItem | None, bubble: MessageBubble | None):
        if item is None or bubble is None:
            return
        available = max(260, self.messages.viewport().width() - 32)
        if bubble.role_label.text() == "你":
            measured = bubble.content_label.fontMetrics().horizontalAdvance(bubble.content_label.text()) + 54
            bubble_width = min(max(150, measured), int(available * 0.72))
        else:
            bubble_width = int(available * 0.86)
        bubble.setFixedWidth(max(150, bubble_width))
        bubble.adjustSize()
        height = max(78, bubble.sizeHint().height())
        row = getattr(bubble, "_message_row", None)
        if row is not None:
            row.setFixedHeight(height)
        item.setSizeHint(QSize(0, height))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for index in range(self.messages.count()):
            item = self.messages.item(index)
            widget = self.messages.itemWidget(item)
            bubble = widget.findChild(MessageBubble) if widget is not None else None
            if bubble is not None:
                self._resize_message_item(item, bubble)

    def _send(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.send_requested.emit(text)
