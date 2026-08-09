from __future__ import annotations

import json

from PySide6.QtCore import QTimer, QSize, Qt, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from app.ui.motion import reveal


class MarkdownLabel(QLabel):
    """A selectable label that renders the assistant's Markdown through Qt."""

    def __init__(self, markdown: str = "", parent=None):
        super().__init__(parent)
        self._markdown = ""
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.set_markdown(markdown)

    def markdown(self) -> str:
        return self._markdown

    def set_markdown(self, markdown: str) -> None:
        self._markdown = str(markdown)
        document = QTextDocument()
        document.setDefaultStyleSheet(
            "body { margin: 0; } "
            "pre { margin: 6px 0; padding: 8px; background: #111923; color: #d5f4e8; "
            "border: 1px solid #365269; border-radius: 6px; } "
            "code { font-family: 'Cascadia Mono', 'Consolas'; color: #bcebd9; } "
            "blockquote { margin: 6px 0; padding-left: 10px; color: #a9c5d2; "
            "border-left: 3px solid #4c8f7f; }"
        )
        document.setMarkdown(self._markdown)
        self.setText(document.toHtml())


class MessageBubble(QFrame):
    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("UserBubble" if role == "user" else "AssistantBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.role_label = QLabel("你" if role == "user" else "LocalMind")
        self.role_label.setObjectName("Muted")
        if role == "assistant":
            self.content_label = MarkdownLabel(text)
        else:
            self.content_label = QLabel(text)
            self.content_label.setWordWrap(True)
            self.content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(5)
        layout.addWidget(self.role_label)
        layout.addWidget(self.content_label)


class CitationLink(QFrame):
    clicked = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("CitationLink")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label = QLabel(text)
        self.label.setObjectName("CitationLabel")
        self.label.setWordWrap(True)
        # The parent frame owns the click.  A selectable QLabel consumes the
        # mouse press first, which makes the source line look clickable but do
        # nothing in the chat UI.
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def click(self) -> None:
        self.clicked.emit()


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
    knowledge_bases_changed = Signal(list)
    citations_requested = Signal(list)

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
        self.options_button = QPushButton("⋯")
        self.options_button.setObjectName("ChatOptionsButton")
        self.options_button.setToolTip("选择本次对话使用的知识库")
        self._knowledge_base_options: list[tuple[str, str]] = []
        self._selected_knowledge_base_ids: list[str] = []
        self._knowledge_menu = QMenu(self)
        self.options_button.setMenu(self._knowledge_menu)
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
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.options_button)
        layout.addLayout(header)
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

    def set_knowledge_bases(self, options: list[tuple[str, str]], selected_ids: list[str]) -> None:
        self._knowledge_base_options = list(options)
        option_ids = {knowledge_base_id for knowledge_base_id, _ in options}
        selected = [item for item in selected_ids if item in option_ids]
        self._selected_knowledge_base_ids = selected or ([options[0][0]] if options else [])
        self._rebuild_knowledge_menu()

    def selected_knowledge_base_ids(self) -> list[str]:
        return list(self._selected_knowledge_base_ids)

    def _rebuild_knowledge_menu(self) -> None:
        self._knowledge_menu.clear()
        heading = self._knowledge_menu.addAction("本次对话使用的知识库")
        heading.setEnabled(False)
        self._knowledge_menu.addSeparator()
        select_all = self._knowledge_menu.addAction("全选")
        select_all.setCheckable(True)
        select_all.setChecked(bool(self._knowledge_base_options) and len(self._selected_knowledge_base_ids) == len(self._knowledge_base_options))
        select_all.triggered.connect(lambda checked: self._toggle_all_knowledge_bases(checked))
        self._knowledge_menu.addSeparator()
        for knowledge_base_id, name in self._knowledge_base_options:
            action = self._knowledge_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(knowledge_base_id in self._selected_knowledge_base_ids)
            action.setData(knowledge_base_id)
            action.triggered.connect(lambda checked, item_id=knowledge_base_id: self._toggle_knowledge_base(item_id, checked))

    def _toggle_all_knowledge_bases(self, checked: bool) -> None:
        if checked:
            self._selected_knowledge_base_ids = [item_id for item_id, _ in self._knowledge_base_options]
        elif self._knowledge_base_options:
            self._selected_knowledge_base_ids = [self._knowledge_base_options[0][0]]
        self._rebuild_knowledge_menu()
        self.knowledge_bases_changed.emit(self.selected_knowledge_base_ids())

    def _toggle_knowledge_base(self, knowledge_base_id: str, checked: bool) -> None:
        selected = list(self._selected_knowledge_base_ids)
        if checked and knowledge_base_id not in selected:
            selected.append(knowledge_base_id)
        elif not checked and knowledge_base_id in selected:
            selected.remove(knowledge_base_id)
        if not selected and self._knowledge_base_options:
            selected = [knowledge_base_id]
        self._selected_knowledge_base_ids = selected
        self._rebuild_knowledge_menu()
        self.knowledge_bases_changed.emit(self.selected_knowledge_base_ids())

    def set_session_title(self, title: str):
        self.title.setText(title.strip() or "新对话")

    def append_user(self, text: str):
        self._append_bubble("user", text)

    def start_assistant(self):
        self._assistant_bubble = self._append_bubble("assistant", "")
        self._assistant_item = getattr(self._assistant_bubble, "_list_item", None)

    def append_token(self, token: str):
        if getattr(self, "_assistant_bubble", None) is not None:
            content_label = self._assistant_bubble.content_label
            if isinstance(content_label, MarkdownLabel):
                content_label.set_markdown(content_label.markdown() + token)
            else:
                content_label.setText(content_label.text() + token)
            self._resize_message_item(self._assistant_item, self._assistant_bubble)

    def append_citations(self, citations: list[dict], animate: bool = True):
        if citations:
            sources = "  来源：" + "、".join(str(item.get("file_name", "未知")) for item in citations)
            label = CitationLink(sources)
            label.clicked.connect(lambda: self.citations_requested.emit(list(citations)))
            item = QListWidgetItem()
            self.messages.addItem(item)
            self.messages.setItemWidget(item, label)
            self._resize_widget_item(item, label, minimum_height=32)
            if animate:
                reveal(label, duration=160, delay=35)
            QTimer.singleShot(0, lambda: self._resize_widget_item(item, label, minimum_height=32))

    def append_tool_call(self, tool_call: dict, animate: bool = True) -> None:
        result = tool_call.get("result", {}) if isinstance(tool_call, dict) else {}
        name = str(tool_call.get("name", "未知工具")) if isinstance(tool_call, dict) else "未知工具"
        source = str(tool_call.get("source", "")) if isinstance(tool_call, dict) else ""
        arguments = tool_call.get("arguments", {}) if isinstance(tool_call, dict) else {}
        if not isinstance(arguments, dict):
            arguments = {}
        if not isinstance(result, dict):
            result = {
                "success": bool(getattr(result, "success", False)),
                "content": list(getattr(result, "content", []) or []),
                "structured_content": getattr(result, "structured_content", None),
                "error": getattr(result, "error", None),
            }
        success = bool(result.get("success"))
        lines = [f"工具调用 · {name}"]
        if source:
            lines.append(f"来源：{source}")
        if arguments:
            lines.append(f"参数：{json.dumps(arguments, ensure_ascii=False)}")
        expression = result.get("expression")
        if expression:
            lines.append(f"表达式：{expression}")
        if success:
            structured = result.get("structured_content")
            content = result.get("content")
            value = result.get("result")
            if structured:
                value = json.dumps(structured, ensure_ascii=False)
            elif content:
                value = "\n".join(str(item) for item in content)
            if value is None:
                value = "调用成功"
            lines.append(f"结果：{value}")
        else:
            error = result.get("error")
            if isinstance(error, dict):
                error = error.get("message")
            lines.append(f"错误：{error or '调用失败'}")
        label = QLabel("\n".join(lines))
        label.setObjectName("ToolCallLabel")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        item = QListWidgetItem()
        self.messages.addItem(item)
        self.messages.setItemWidget(item, label)
        self._resize_widget_item(item, label, minimum_height=72, extra_height=12)
        if animate:
            reveal(label, duration=160, delay=50)
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
            if message.citations and not message.tool_calls:
                self.append_citations(message.citations, animate=False)
            for tool_call in message.tool_calls:
                self.append_tool_call(tool_call, animate=False)

    def _append_bubble(self, role: str, text: str) -> MessageBubble:
        item = QListWidgetItem()
        bubble = MessageBubble(role, text)
        row = QWidget()
        row.setObjectName("MessageRow")
        row_layout = QHBoxLayout(row)
        # Keep the user bubble clear of the always-visible vertical scrollbar.
        row_layout.setContentsMargins(0, 0, 32, 0)
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
        reveal(row, duration=180, delay=20)
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
        available = max(260, self.messages.viewport().width() - 48)
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
