from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    name: str
    category: str
    description: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = False
    icon_text: str = "◇"
    recent_calls: tuple[str, ...] = field(default_factory=tuple)


DEFAULT_TOOL_DEFINITIONS = [
    ToolDefinition(
        id="calculator",
        name="高级计算器",
        category="计算",
        description="执行算术、三角函数、对数和矩阵计算。",
        capabilities=("算术", "三角函数", "对数", "矩阵", "单位换算"),
        enabled=True,
        icon_text="∑",
        recent_calls=("sin(30°) + 125 × 8", "det([[1,2],[3,4]])", "log10(1000)"),
    ),
    ToolDefinition(
        id="semantic-search",
        name="语义检索",
        category="检索",
        description="基于语义理解检索相似内容，支持向量化与重排。",
        capabilities=("查询向量", "相似度", "Top-K"),
        icon_text="⌕",
    ),
    ToolDefinition(
        id="document-parser",
        name="文档解析",
        category="文档",
        description="解析多种格式文档，提取结构化内容与元数据。",
        capabilities=("PDF", "DOCX", "Markdown"),
        icon_text="▤",
    ),
    ToolDefinition(
        id="knowledge-retriever",
        name="知识库检索",
        category="检索",
        description="在本地知识库中检索相关信息，支持过滤与排序。",
        capabilities=("知识库", "元数据", "引用"),
        icon_text="◉",
    ),
    ToolDefinition(
        id="file-inspector",
        name="文件检查",
        category="文档",
        description="检查文件完整性、安全性与哈希值，识别潜在风险。",
        capabilities=("哈希", "完整性", "本地文件"),
        icon_text="✓",
    ),
    ToolDefinition(
        id="unit-converter",
        name="单位换算",
        category="计算",
        description="支持长度、质量、温度和时间等常用单位换算。",
        capabilities=("长度", "质量", "温度"),
        icon_text="↔",
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
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

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
        layout.addWidget(description, 1)
        status_row = QHBoxLayout()
        status = QLabel("●  已启用" if tool.enabled else "●  未接入")
        status.setObjectName("ToolEnabledStatus" if tool.enabled else "ToolDisabledStatus")
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
    test_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolDetailsPanel")
        self.current_tool: ToolDefinition | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(10)

        heading = QLabel("工具详情")
        heading.setObjectName("ContextTitle")
        layout.addWidget(heading)
        self.title_label = QLabel("选择一个工具")
        self.title_label.setObjectName("ToolDetailsTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        self.status_label = QLabel("")
        self.status_label.setObjectName("ToolDetailsStatus")
        layout.addWidget(self.status_label)
        self.description_label = QLabel("点击中间的工具卡片查看详细信息。")
        self.description_label.setObjectName("ToolDetailsDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)
        self.capabilities_label = QLabel("")
        self.capabilities_label.setObjectName("ToolCapabilities")
        self.capabilities_label.setWordWrap(True)
        layout.addWidget(self.capabilities_label)
        self.example_label = QLabel("")
        self.example_label.setObjectName("ToolExample")
        self.example_label.setWordWrap(True)
        layout.addWidget(self.example_label)
        recent_title = QLabel("最近调用记录")
        recent_title.setObjectName("ToolSectionTitle")
        layout.addWidget(recent_title)
        self.recent_label = QLabel("暂无调用记录")
        self.recent_label.setObjectName("ToolRecentCalls")
        self.recent_label.setWordWrap(True)
        layout.addWidget(self.recent_label)
        layout.addStretch(1)
        buttons = QHBoxLayout()
        self.configure_button = QPushButton("配置工具")
        self.test_button = QPushButton("测试调用")
        self.test_button.setObjectName("PrimaryButton")
        buttons.addWidget(self.configure_button)
        buttons.addWidget(self.test_button)
        layout.addLayout(buttons)
        self.configure_button.clicked.connect(self._emit_configure)
        self.test_button.clicked.connect(self._emit_test)

    def set_tool(self, tool: ToolDefinition | None) -> None:
        self.current_tool = tool
        if tool is None:
            self.title_label.setText("选择一个工具")
            self.status_label.clear()
            self.description_label.setText("点击中间的工具卡片查看详细信息。")
            self.capabilities_label.clear()
            self.example_label.clear()
            self.recent_label.setText("暂无调用记录")
            self.configure_button.setEnabled(False)
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
        self.recent_label.setText(
            "\n".join(f"{index}. {call}" for index, call in enumerate(tool.recent_calls, 1))
            if tool.recent_calls
            else "暂无调用记录"
        )
        self.configure_button.setEnabled(True)
        self.test_button.setEnabled(tool.enabled)

    def _emit_configure(self):
        if self.current_tool:
            self.configure_requested.emit(self.current_tool.id)

    def _emit_test(self):
        if self.current_tool and self.current_tool.enabled:
            self.test_requested.emit(self.current_tool.id)


class ToolCenterPage(QFrame):
    tool_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolCenterPage")
        self._tools: dict[str, ToolDefinition] = {}
        self._cards: dict[str, ToolCard] = {}
        self._selected_tool_id: str | None = None
        self.category_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        title = QLabel("工具中心")
        title.setObjectName("Title")
        layout.addWidget(title)
        subtitle = QLabel("管理本地模型可以调用的工具")
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

        filters = QHBoxLayout()
        for category in ("全部", "已启用", "计算", "检索", "文档"):
            button = QPushButton(category)
            button.setCheckable(True)
            button.setObjectName("ToolFilterButton")
            button.clicked.connect(lambda checked, value=category: self._set_category(value))
            self.category_buttons[category] = button
            filters.addWidget(button)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setHorizontalSpacing(12)
        self.cards_layout.setVerticalSpacing(12)
        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, 1)
        self.footer_label = QLabel("")
        self.footer_label.setObjectName("Muted")
        layout.addWidget(self.footer_label)
        self.search_input.textChanged.connect(self._refresh_visibility)
        self.category_buttons["全部"].setChecked(True)

    def set_tools(self, tools: list[ToolDefinition]) -> None:
        self._tools = {tool.id: tool for tool in tools}
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()
        for index, tool in enumerate(tools):
            card = ToolCard(tool)
            card.clicked.connect(self.select_tool)
            self._cards[tool.id] = card
            self.cards_layout.addWidget(card, index // 3, index % 3)
        self.cards_layout.setColumnStretch(0, 1)
        self.cards_layout.setColumnStretch(1, 1)
        self.cards_layout.setColumnStretch(2, 1)
        self.footer_label.setText(
            f"共 {len(tools)} 个工具 · 已启用 {sum(tool.enabled for tool in tools)} 个"
        )
        if tools:
            self.select_tool(self._selected_tool_id if self._selected_tool_id in self._tools else tools[0].id, emit=False)
        self._refresh_visibility()

    def tool(self, tool_id: str) -> ToolDefinition | None:
        return self._tools.get(tool_id)

    def card(self, tool_id: str) -> ToolCard:
        return self._cards[tool_id]

    def selected_tool_id(self) -> str | None:
        return self._selected_tool_id

    def visible_tool_ids(self) -> list[str]:
        return [tool_id for tool_id, card in self._cards.items() if not card.isHidden()]

    def select_tool(self, tool_id: str, emit: bool = True) -> None:
        if tool_id not in self._tools:
            return
        self._selected_tool_id = tool_id
        for current_id, card in self._cards.items():
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
                or tool.category == category
            )
            card.setVisible(matches_query and matches_category)
