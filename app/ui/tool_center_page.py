from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from app.models import ToolDefinition


def _registered_tool_definitions() -> list[ToolDefinition]:
    """Build cards from the tools that are actually exposed by the project."""
    from tools.calculator import calculator_tool

    return [
        ToolDefinition(
            id=calculator_tool.name,
            name="高级计算器",
            category="计算",
            description=calculator_tool.description,
            capabilities=("算术", "三角函数", "对数", "矩阵", "方程", "单位换算"),
            enabled=True,
            icon_text="∑",
            recent_calls=("sin(30°) + 125 × 8", "det([[1,2],[3,4]])", "log10(1000)"),
        ),
    ]


DEFAULT_TOOL_DEFINITIONS = _registered_tool_definitions()


# These are real local services, but they are not model-callable Agent Tools.
DEFAULT_LOCAL_CAPABILITIES = [
    ToolDefinition(
        id="document-parser",
        name="文档解析",
        category="文档",
        description="读取 PDF、DOCX、Markdown 等本地文档并提取文本。",
        capabilities=("PDF", "DOCX", "Markdown"),
        icon_text="▤",
        kind="capability",
    ),
    ToolDefinition(
        id="chunking",
        name="文本分段",
        category="文档",
        description="按照自动、自定义或层级策略切分文档内容。",
        capabilities=("自动分段", "自定义分段", "按层级分段"),
        icon_text="⌘",
        kind="capability",
    ),
    ToolDefinition(
        id="embedding",
        name="Embedding 向量化",
        category="检索",
        description="把查询和文档转换为向量，供语义检索使用。",
        capabilities=("本地模型", "384 维向量", "余弦相似度"),
        icon_text="✣",
        kind="capability",
    ),
    ToolDefinition(
        id="knowledge-retrieval",
        name="知识库检索",
        category="检索",
        description="在当前知识库中检索相关片段并生成回答依据。",
        capabilities=("Top-K", "元数据", "引用"),
        icon_text="⌕",
        kind="capability",
    ),
    ToolDefinition(
        id="chroma-store",
        name="Chroma 向量存储",
        category="检索",
        description="在本机持久化保存文档向量和检索元数据。",
        capabilities=("Collection", "持久化", "本地存储"),
        icon_text="◉",
        kind="capability",
    ),
]


class ToolCard(QFrame):
    clicked = Signal(str)

    def __init__(self, tool: ToolDefinition, parent=None):
        super().__init__(parent)
        self.tool = tool
        self.setObjectName("ToolCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # A filtered grid may have only one card.  Keep every card compact so
        # Qt does not stretch that single result to the full scroll viewport.
        self.setFixedHeight(184)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(7)
        icon = QLabel(tool.icon_text)
        icon.setObjectName("ToolIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(44, 44)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignLeft)
        title = QLabel(tool.name)
        title.setObjectName("ToolCardTitle")
        layout.addWidget(title)
        description = QLabel(tool.description)
        description.setObjectName("ToolCardDescription")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        description.setMaximumHeight(44)
        layout.addWidget(description)
        status_row = QHBoxLayout()
        if tool.kind == "capability":
            status_text, status_name = "●  系统能力", "ToolCapabilityStatus"
        elif tool.enabled:
            status_text, status_name = "●  已接入", "ToolEnabledStatus"
        else:
            status_text, status_name = "●  未接入", "ToolDisabledStatus"
        status = QLabel(status_text)
        status.setObjectName(status_name)
        status_row.addWidget(status)
        status_row.addStretch(1)
        layout.addLayout(status_row)
        self.status_label = status

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tool.id)
        super().mousePressEvent(event)


class ToolDetailsPanel(QFrame):
    configure_requested = Signal(str)
    edit_display_requested = Signal(str)
    test_requested = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolDetailsPanel")
        self.current_tool: ToolDefinition | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(10)

        self.details_scroll_area = QScrollArea()
        self.details_scroll_area.setObjectName("ToolDetailsScrollArea")
        self.details_scroll_area.setWidgetResizable(True)
        self.details_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.details_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        details_content = QWidget()
        details_content.setObjectName("ToolDetailsContent")
        details_content.setAutoFillBackground(True)
        details_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        details_layout = QVBoxLayout(details_content)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(10)

        heading = QLabel("工具详情")
        heading.setObjectName("ContextTitle")
        details_layout.addWidget(heading)
        self.title_label = QLabel("选择一个工具")
        self.title_label.setObjectName("ToolDetailsTitle")
        self.title_label.setWordWrap(True)
        details_layout.addWidget(self.title_label)
        self.status_label = QLabel("")
        self.status_label.setObjectName("ToolDetailsStatus")
        details_layout.addWidget(self.status_label)
        self.description_label = QLabel("点击中间的工具卡片查看详细信息。")
        self.description_label.setObjectName("ToolDetailsDescription")
        self.description_label.setWordWrap(True)
        details_layout.addWidget(self.description_label)
        self.capabilities_label = QLabel("")
        self.capabilities_label.setObjectName("ToolCapabilities")
        self.capabilities_label.setWordWrap(True)
        details_layout.addWidget(self.capabilities_label)
        self.example_label = QLabel("")
        self.example_label.setObjectName("ToolExample")
        self.example_label.setWordWrap(True)
        details_layout.addWidget(self.example_label)
        self.schema_label = QLabel("")
        self.schema_label.setObjectName("ToolSchema")
        self.schema_label.setWordWrap(True)
        details_layout.addWidget(self.schema_label)
        self.arguments_input = QPlainTextEdit("{}")
        self.arguments_input.setObjectName("ToolArgumentsInput")
        self.arguments_input.setPlaceholderText('{"text": "要传给工具的内容"}')
        self.arguments_input.setFixedHeight(92)
        details_layout.addWidget(self.arguments_input)
        recent_title = QLabel("最近调用记录")
        recent_title.setObjectName("ToolSectionTitle")
        details_layout.addWidget(recent_title)
        self.recent_label = QLabel("暂无调用记录")
        self.recent_label.setObjectName("ToolRecentCalls")
        self.recent_label.setWordWrap(True)
        details_layout.addWidget(self.recent_label)
        self.test_result_label = QLabel("")
        self.test_result_label.setObjectName("ToolTestResult")
        self.test_result_label.setWordWrap(True)
        self.test_result_label.hide()
        details_layout.addWidget(self.test_result_label)
        self.details_scroll_area.setWidget(details_content)
        layout.addWidget(self.details_scroll_area, 1)
        buttons = QHBoxLayout()
        self.edit_display_button = QPushButton("编辑显示信息")
        self.test_button = QPushButton("测试调用")
        self.test_button.setObjectName("PrimaryButton")
        buttons.addWidget(self.edit_display_button)
        buttons.addWidget(self.test_button)
        layout.addLayout(buttons)
        self.edit_display_button.clicked.connect(self._emit_edit_display)
        self.test_button.clicked.connect(self._emit_test)

    def set_tool(self, tool: ToolDefinition | None) -> None:
        self.current_tool = tool
        if tool is None:
            self.title_label.setText("选择一个工具")
            self.status_label.clear()
            self.description_label.setText("点击中间的工具卡片查看详细信息。")
            self.capabilities_label.clear()
            self.example_label.clear()
            self.schema_label.clear()
            self.arguments_input.hide()
            self.recent_label.setText("暂无调用记录")
            self.test_result_label.clear()
            self.test_result_label.hide()
            self.edit_display_button.setVisible(False)
            self.edit_display_button.setEnabled(False)
            self.test_button.setEnabled(False)
            return
        self.title_label.setText(tool.name)
        self.status_label.setText("●  已启用" if tool.enabled else "○  尚未接入")
        self.status_label.setProperty("enabled", tool.enabled)
        self.description_label.setText(tool.description)
        self.capabilities_label.setText("能力：" + "  ·  ".join(tool.capabilities))
        self.example_label.setText(
            "示例：" + (tool.recent_calls[0] if tool.recent_calls else "暂无示例")
        )
        if tool.kind == "mcp":
            self.schema_label.setText("输入参数：\n" + json.dumps(tool.input_schema, ensure_ascii=False, indent=2))
            self.arguments_input.setPlainText(
                json.dumps(self._sample_arguments(tool.input_schema), ensure_ascii=False, indent=2)
            )
            self.arguments_input.show()
        else:
            self.schema_label.clear()
            self.arguments_input.hide()
        self.recent_label.setText(
            "\n".join(f"{index}. {call}" for index, call in enumerate(tool.recent_calls, 1))
            if tool.recent_calls
            else "暂无调用记录"
        )
        self.test_result_label.clear()
        self.test_result_label.hide()
        is_registered_tool = tool.kind in {"tool", "mcp"}
        is_mcp_tool = tool.kind == "mcp"
        self.edit_display_button.setVisible(is_mcp_tool)
        self.edit_display_button.setEnabled(is_mcp_tool)
        self.test_button.setVisible(is_registered_tool)
        self.test_button.setEnabled(is_registered_tool and tool.enabled)

    def _emit_configure(self):
        if self.current_tool:
            self.configure_requested.emit(self.current_tool.id)

    def _emit_edit_display(self):
        if self.current_tool and self.current_tool.kind == "mcp":
            self.edit_display_requested.emit(self.current_tool.id)

    def _emit_test(self):
        if self.current_tool and self.current_tool.enabled:
            arguments: dict = {}
            if self.current_tool.kind == "mcp":
                try:
                    arguments = json.loads(self.arguments_input.toPlainText() or "{}")
                except json.JSONDecodeError as error:
                    self.set_test_result(f"JSON 参数格式错误：{error}", success=False)
                    return
                if not isinstance(arguments, dict):
                    self.set_test_result("JSON 参数必须是一个对象，例如 {\"text\": \"你好\"}。", success=False)
                    return
            self.test_requested.emit(self.current_tool.id, arguments)

    def set_test_result(self, text: str, success: bool = True) -> None:
        self.test_result_label.setText(text)
        self.test_result_label.setProperty("success", success)
        self.test_result_label.style().unpolish(self.test_result_label)
        self.test_result_label.style().polish(self.test_result_label)
        self.test_result_label.show()

    @staticmethod
    def _sample_arguments(input_schema: dict) -> dict:
        """Offer a safe editable example for manual MCP testing."""
        schema = dict(input_schema or {})
        if isinstance(schema.get("parameters"), dict):
            schema = dict(schema["parameters"])
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return {}
        if "city_name" in properties:
            return {"city_name": "Shanghai"}
        if "location_name" in properties:
            return {"location_name": "Shanghai"}
        if "query" in properties:
            return {"query": "Shanghai"}
        if "timezone" in properties:
            return {"timezone": "Asia/Shanghai"}
        if {"source_timezone", "time", "target_timezone"}.issubset(properties):
            return {
                "source_timezone": "Asia/Shanghai",
                "time": "12:00:00",
                "target_timezone": "Asia/Tokyo",
            }
        return {}


class ToolCenterPage(QFrame):
    tool_selected = Signal(str)
    mcp_servers_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolCenterPage")
        self._tools: dict[str, ToolDefinition] = {}
        self._capabilities: dict[str, ToolDefinition] = {}
        self._cards: dict[str, ToolCard] = {}
        self._capability_cards: dict[str, ToolCard] = {}
        self._selected_tool_id: str | None = None
        self.category_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        title = QLabel("工具中心")
        title.setObjectName("Title")
        layout.addWidget(title)
        subtitle = QLabel("真实可调用工具与本地知识流程能力")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索工具名称或描述")
        controls.addWidget(self.search_input, 1)
        grid_button = QPushButton("▦")
        grid_button.setObjectName("QuietButton")
        grid_button.setToolTip("网格视图")
        list_button = QPushButton("☷")
        list_button.setObjectName("QuietButton")
        list_button.setToolTip("列表视图")
        controls.addWidget(grid_button)
        controls.addWidget(list_button)
        layout.addLayout(controls)

        self.mcp_servers_button = QPushButton("管理 MCP Server")
        self.mcp_servers_button.setObjectName("QuietButton")
        self.mcp_servers_button.clicked.connect(self.mcp_servers_requested)
        layout.addWidget(self.mcp_servers_button, 0, Qt.AlignmentFlag.AlignLeft)

        filters = QHBoxLayout()
        for category in ("全部", "已启用", "本地工具", "远程工具", "本地能力"):
            button = QPushButton(category)
            button.setCheckable(True)
            button.setObjectName("ToolFilterButton")
            button.clicked.connect(lambda checked, value=category: self._set_category(value))
            self.category_buttons[category] = button
            filters.addWidget(button)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.cards_scroll_area = QScrollArea()
        self.cards_scroll_area.setObjectName("ToolCardsScrollArea")
        self.cards_scroll_area.setWidgetResizable(True)
        self.cards_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area = self.cards_scroll_area
        self.cards_container = QWidget()
        self.cards_container.setObjectName("ToolCardsContent")
        self.cards_container.setAutoFillBackground(True)
        self.cards_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        container_layout = QVBoxLayout(self.cards_container)
        container_layout.setContentsMargins(0, 4, 0, 4)
        container_layout.setSpacing(8)
        self.tools_section_label = QLabel("已接入工具")
        self.tools_section_label.setObjectName("ToolSectionTitle")
        container_layout.addWidget(self.tools_section_label)
        self.tools_grid_container = QWidget()
        self.tools_grid_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self.cards_layout = QGridLayout(self.tools_grid_container)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setHorizontalSpacing(12)
        self.cards_layout.setVerticalSpacing(12)
        container_layout.addWidget(self.tools_grid_container)
        self.capabilities_section_label = QLabel("本地能力")
        self.capabilities_section_label.setObjectName("ToolSectionTitle")
        container_layout.addWidget(self.capabilities_section_label)
        self.capabilities_hint = QLabel("这些能力由知识库流程使用，不会伪装成模型可调用工具。")
        self.capabilities_hint.setObjectName("Muted")
        self.capabilities_hint.setWordWrap(True)
        container_layout.addWidget(self.capabilities_hint)
        self.capabilities_grid_container = QWidget()
        self.capabilities_grid_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self.capabilities_layout = QGridLayout(self.capabilities_grid_container)
        self.capabilities_layout.setContentsMargins(0, 4, 0, 4)
        self.capabilities_layout.setHorizontalSpacing(12)
        self.capabilities_layout.setVerticalSpacing(12)
        container_layout.addWidget(self.capabilities_grid_container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.cards_scroll_area, 1)
        self.footer_label = QLabel("")
        self.footer_label.setObjectName("Muted")
        layout.addWidget(self.footer_label)
        self.search_input.textChanged.connect(self._refresh_visibility)
        self.category_buttons["全部"].setChecked(True)

    def set_tools(
        self,
        tools: list[ToolDefinition],
        capabilities: list[ToolDefinition] | None = None,
    ) -> None:
        # Rebuilding the registry must dispose the previous widgets. Merely
        # taking items out of a Qt layout leaves their parent widgets visible,
        # which creates ghost cards underneath the new grid.
        old_cards = [*self._cards.values(), *self._capability_cards.values()]
        for card in old_cards:
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self._tools = {tool.id: tool for tool in tools}
        self._capabilities = {
            capability.id: capability
            for capability in (capabilities if capabilities is not None else DEFAULT_LOCAL_CAPABILITIES)
        }
        self._clear_layout(self.cards_layout)
        self._clear_layout(self.capabilities_layout)
        self._cards.clear()
        self._capability_cards.clear()
        for tool in tools:
            card = ToolCard(tool)
            card.clicked.connect(self.select_tool)
            self._cards[tool.id] = card
        for capability in self._capabilities.values():
            card = ToolCard(capability)
            card.clicked.connect(self.select_tool)
            self._capability_cards[capability.id] = card
        self._set_grid_stretch(self.cards_layout)
        self._set_grid_stretch(self.capabilities_layout)
        self.footer_label.setText(
            f"{len(tools)} 个可调用工具 · {len(self._capabilities)} 项本地能力 · "
            f"已接入 {sum(tool.enabled for tool in tools)} 个"
        )
        all_definitions = {**self._tools, **self._capabilities}
        if all_definitions:
            selected_id = self._selected_tool_id if self._selected_tool_id in all_definitions else next(iter(all_definitions))
            self.select_tool(selected_id, emit=False)
        self._refresh_visibility()

    def tool(self, tool_id: str) -> ToolDefinition | None:
        return self._tools.get(tool_id) or self._capabilities.get(tool_id)

    def card(self, tool_id: str) -> ToolCard:
        return self._cards.get(tool_id) or self._capability_cards[tool_id]

    def selected_tool_id(self) -> str | None:
        return self._selected_tool_id

    def visible_tool_ids(self) -> list[str]:
        return [tool_id for tool_id, card in self._cards.items() if not card.isHidden()]

    def visible_capability_ids(self) -> list[str]:
        return [tool_id for tool_id, card in self._capability_cards.items() if not card.isHidden()]

    def card_grid_position(self, tool_id: str) -> tuple[int, int]:
        return self._grid_position(self.cards_layout, self.card(tool_id))

    def select_tool(self, tool_id: str, emit: bool = True) -> None:
        if tool_id not in self._tools and tool_id not in self._capabilities:
            return
        self._selected_tool_id = tool_id
        for current_id, card in {**self._cards, **self._capability_cards}.items():
            card.set_selected(current_id == tool_id)
        if emit:
            self.tool_selected.emit(tool_id)

    def _set_category(self, category: str) -> None:
        for name, button in self.category_buttons.items():
            button.setChecked(name == category)
        self._refresh_visibility()

    def _refresh_visibility(self) -> None:
        query = self.search_input.text().strip().casefold()
        category = next((name for name, button in self.category_buttons.items() if button.isChecked()), "全部")
        for tool_id, card in self._cards.items():
            tool = self._tools[tool_id]
            searchable = " ".join((tool.name, tool.description, tool.category)).casefold()
            matches_query = not query or query in searchable
            matches_category = (
                category == "全部"
                or (category == "已启用" and tool.enabled)
                or (category == "本地工具" and tool.kind != "mcp")
                or (category == "远程工具" and tool.kind == "mcp")
            )
            card.setVisible(matches_query and matches_category)
        for capability_id, card in self._capability_cards.items():
            capability = self._capabilities[capability_id]
            searchable = " ".join((capability.name, capability.description, capability.category)).casefold()
            matches_query = not query or query in searchable
            matches_category = category in {"全部", "本地能力"}
            card.setVisible(matches_query and matches_category)
        self._reflow_visible(self.cards_layout, self._cards)
        self._reflow_visible(self.capabilities_layout, self._capability_cards)
        self.tools_grid_container.setVisible(bool(self.visible_tool_ids()))
        self.tools_section_label.setVisible(bool(self.visible_tool_ids()))
        self.capabilities_grid_container.setVisible(bool(self.visible_capability_ids()))
        self.capabilities_section_label.setVisible(bool(self.visible_capability_ids()))
        self.capabilities_hint.setVisible(bool(self.visible_capability_ids()))
        # Repaint synchronously after a display-name edit so cards never need
        # a manual page refresh to reappear.
        self.cards_container.updateGeometry()
        self.cards_scroll_area.viewport().update()

    @staticmethod
    def _clear_layout(layout: QGridLayout) -> None:
        while layout.count():
            layout.takeAt(0)

    @staticmethod
    def _set_grid_stretch(layout: QGridLayout) -> None:
        for column in range(3):
            layout.setColumnStretch(column, 1)

    @staticmethod
    def _reflow_visible(layout: QGridLayout, cards: dict[str, ToolCard]) -> None:
        while layout.count():
            layout.takeAt(0)
        visible_cards = [card for card in cards.values() if not card.isHidden()]
        for index, card in enumerate(visible_cards):
            layout.addWidget(card, index // 3, index % 3)

    @staticmethod
    def _grid_position(layout: QGridLayout, widget: QWidget) -> tuple[int, int]:
        index = layout.indexOf(widget)
        if index < 0:
            return (-1, -1)
        row, column, _row_span, _column_span = layout.getItemPosition(index)
        return row, column
