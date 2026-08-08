import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QSignalSpy

from app.ui.tool_center_page import ToolCenterPage, ToolDefinition, ToolDetailsPanel


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
    page.category_buttons["检索"].click()
    assert page.visible_tool_ids() == ["retriever"]
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
    assert "已启用" in page.card("calculator").status_label.text()
    assert "未接入" in page.card("retriever").status_label.text()
    page.close()
