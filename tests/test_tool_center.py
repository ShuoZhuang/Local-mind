import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QSignalSpy
from PySide6.QtCore import Qt

from app.ui.tool_center_page import (
    DEFAULT_LOCAL_CAPABILITIES,
    DEFAULT_TOOL_DEFINITIONS,
    ToolCenterPage,
    ToolDefinition,
    ToolDetailsPanel,
    ToolCard,
)


def app():
    return QApplication.instance() or QApplication([])


def definitions():
    return [
        ToolDefinition(
            id="calculator",
            name="高级计算器",
            category="计算",
            description="执行算术、三角函数和矩阵计算。",
            capabilities=("算术", "三角函数"),
            enabled=True,
            icon_text="∑",
        ),
        ToolDefinition(
            id="retriever",
            name="知识库检索",
            category="检索",
            description="在本地知识库中检索相关内容。",
            capabilities=("语义检索",),
            enabled=False,
            icon_text="⌕",
        ),
    ]


def test_tool_center_filters_cards_by_search_and_category():
    app()
    page = ToolCenterPage()
    page.set_tools(definitions())

    page.search_input.setText("高级")
    assert page.visible_tool_ids() == ["calculator"]

    page.search_input.clear()
    page.category_buttons["已启用"].click()
    assert page.visible_tool_ids() == ["calculator"]
    page.close()


def test_tool_center_emits_selected_tool_and_details_update():
    app()
    page = ToolCenterPage()
    panel = ToolDetailsPanel()
    page.set_tools(definitions())
    spy = QSignalSpy(page.tool_selected)

    page.select_tool("calculator")
    assert spy.count() == 1
    assert spy.at(0)[0] == "calculator"
    panel.set_tool(page.tool("calculator"))
    assert panel.title_label.text() == "高级计算器"
    assert "三角函数" in panel.capabilities_label.text()
    page.close()
    panel.close()


def test_tool_center_has_all_filter_and_only_enabled_state_is_enabled():
    app()
    page = ToolCenterPage()
    page.set_tools(definitions())

    page.category_buttons["全部"].click()
    assert page.visible_tool_ids() == ["calculator", "retriever"]
    assert "已接入" in page.card("calculator").status_label.text()
    assert "未接入" in page.card("retriever").status_label.text()
    page.close()


def test_tool_center_uses_only_registered_tools_and_separates_local_capabilities():
    assert [tool.id for tool in DEFAULT_TOOL_DEFINITIONS] == ["calculator"]
    assert all(tool.kind == "tool" for tool in DEFAULT_TOOL_DEFINITIONS)
    assert {capability.id for capability in DEFAULT_LOCAL_CAPABILITIES} == {
        "document-parser",
        "chunking",
        "embedding",
        "knowledge-retrieval",
        "chroma-store",
    }
    assert all(capability.kind == "capability" for capability in DEFAULT_LOCAL_CAPABILITIES)


def test_tool_center_simplifies_filters_and_separates_enabled_tools_from_local_capabilities():
    app()
    page = ToolCenterPage()
    page.set_tools(definitions(), DEFAULT_LOCAL_CAPABILITIES)

    assert list(page.category_buttons) == [
        "全部",
        "已启用",
        "本地工具",
        "远程工具",
        "本地能力",
    ]
    assert "计算" not in page.category_buttons
    assert "检索" not in page.category_buttons
    assert "文档" not in page.category_buttons

    page.category_buttons["已启用"].click()
    assert page.visible_tool_ids() == ["calculator"]
    assert page.visible_capability_ids() == []

    page.category_buttons["本地能力"].click()
    assert page.visible_tool_ids() == []
    assert page.visible_capability_ids() == [
        "document-parser",
        "chunking",
        "embedding",
        "knowledge-retrieval",
        "chroma-store",
    ]
    page.close()


def test_tool_center_filters_mixed_tools_by_kind_and_keeps_capabilities_local():
    app()
    page = ToolCenterPage()
    mixed_tools = [
        ToolDefinition(
            id="calculator",
            name="高级计算器",
            category="远程工具",
            description="执行算术、三角函数和矩阵计算。",
            capabilities=("算术",),
            enabled=True,
            icon_text="∑",
            kind="tool",
        ),
        ToolDefinition(
            id="mcp:demo:repeat",
            name="重复工具",
            category="本地工具",
            description="由演示 MCP 服务提供的重复工具。",
            capabilities=("文本重复",),
            enabled=True,
            icon_text="↗",
            kind="mcp",
        ),
    ]
    capability_ids = [capability.id for capability in DEFAULT_LOCAL_CAPABILITIES]
    page.set_tools(mixed_tools, DEFAULT_LOCAL_CAPABILITIES)

    assert list(page.category_buttons) == [
        "全部",
        "已启用",
        "本地工具",
        "远程工具",
        "本地能力",
    ]

    page.category_buttons["本地工具"].click()
    assert page.visible_tool_ids() == ["calculator"]
    assert page.visible_capability_ids() == []

    page.category_buttons["远程工具"].click()
    assert page.visible_tool_ids() == ["mcp:demo:repeat"]
    assert page.visible_capability_ids() == []

    page.category_buttons["本地能力"].click()
    assert page.visible_tool_ids() == []
    assert page.visible_capability_ids() == capability_ids

    page.category_buttons["已启用"].click()
    assert page.visible_tool_ids() == ["calculator", "mcp:demo:repeat"]
    assert page.visible_capability_ids() == []

    page.category_buttons["全部"].click()
    assert page.visible_tool_ids() == ["calculator", "mcp:demo:repeat"]
    assert page.visible_capability_ids() == capability_ids
    page.close()


def test_tool_center_reflows_cards_after_filtering():
    application = app()
    page = ToolCenterPage()
    page.set_tools(definitions())

    page.category_buttons["已启用"].click()

    assert page.visible_tool_ids() == ["calculator"]
    assert page.card_grid_position("calculator") == (0, 0)
    page.close()


def test_tool_center_disposes_previous_cards_when_registry_refreshes():
    page = ToolCenterPage()
    page.set_tools(definitions(), DEFAULT_LOCAL_CAPABILITIES)
    page.set_tools(definitions(), DEFAULT_LOCAL_CAPABILITIES)

    assert len(page.cards_container.findChildren(ToolCard)) == 2 + len(DEFAULT_LOCAL_CAPABILITIES)
    page.close()


def test_tool_details_only_exposes_test_action_for_real_tools():
    application = app()
    panel = ToolDetailsPanel()
    panel.set_tool(DEFAULT_TOOL_DEFINITIONS[0])
    assert not panel.test_button.isHidden()
    assert panel.test_button.isEnabled()
    panel.set_tool(DEFAULT_LOCAL_CAPABILITIES[0])
    assert panel.test_button.isHidden()
    panel.close()


def test_tool_center_card_viewport_is_vertical_scroll_only():
    app()
    page = ToolCenterPage()

    assert page.cards_scroll_area.verticalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.cards_scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    page.close()


def test_tool_cards_keep_a_compact_fixed_height_after_filtering():
    app()
    page = ToolCenterPage()
    page.set_tools(definitions())

    list(page.category_buttons.values())[1].click()
    card = page.card("calculator")

    assert card.minimumHeight() == card.maximumHeight()
    assert card.maximumHeight() <= 190
    page.close()


def test_single_tool_card_stays_at_the_top_of_the_scroll_viewport():
    application = app()
    page = ToolCenterPage()
    page.resize(1200, 900)
    page.set_tools([definitions()[0]], [])
    page.show()
    application.processEvents()

    assert page.tools_grid_container.y() < 50
    assert page.card("calculator").y() < 20
    page.close()


def test_tool_center_keeps_remote_cards_visible_after_rebuilding_tools():
    app()
    page = ToolCenterPage()
    remote = ToolDefinition(
        id="mcp:weather:get_current_conditions",
        name="当前天气",
        category="MCP",
        description="查询指定城市的实时天气。",
        enabled=True,
        kind="mcp",
    )

    page.set_tools([remote])
    page.category_buttons["远程工具"].click()
    page.set_tools([remote])

    assert page.visible_tool_ids() == [remote.id]
    assert page.cards_layout.count() == 1
    page.close()


def test_tool_details_keep_test_button_outside_scrollable_content():
    app()
    panel = ToolDetailsPanel()
    panel.set_tool(
        ToolDefinition(
            id="mcp:mcp-demo:get_forecast",
            name="get_forecast",
            category="MCP",
            description="long description",
            enabled=True,
            kind="mcp",
            input_schema={"type": "object", "properties": {"location": {"type": "string"}}},
        )
    )

    assert panel.details_scroll_area.widget().findChild(type(panel.test_button)) is None
    assert panel.test_button.parentWidget() is not panel.details_scroll_area.widget()
    panel.close()


def test_weather_tool_test_input_starts_with_a_city_example():
    app()
    panel = ToolDetailsPanel()
    panel.set_tool(
        ToolDefinition(
            id="mcp:weather:get_current_conditions",
            name="当前天气",
            category="MCP",
            description="查询天气",
            enabled=True,
            kind="mcp",
            input_schema={
                "type": "object",
                "properties": {"city_name": {"type": "string"}},
            },
        )
    )

    assert '"city_name": "Shanghai"' in panel.arguments_input.toPlainText()
    panel.close()
