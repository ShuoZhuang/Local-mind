import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QSignalSpy

from app.models import ToolDefinition
from app.services.storage import LocalStateStore
from app.ui.mcp_server_dialog import MCPServerDialog
from app.ui.mcp_tool_display_dialog import MCPToolDisplayDialog
from app.ui.tool_center_page import ToolDetailsPanel


def app():
    return QApplication.instance() or QApplication([])


def test_mcp_server_dialog_validates_command_and_saves_server(tmp_path, monkeypatch):
    app()
    store = LocalStateStore(tmp_path)
    monkeypatch.setattr(
        "app.ui.mcp_server_dialog.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    dialog = MCPServerDialog(store)
    dialog.name_input.setText("演示服务")
    dialog.command_input.setText("python")
    dialog.arguments_input.setPlainText('["-m", "tests.mcp_test_server"]')

    dialog.save_current_server()

    assert store.list_mcp_servers()[0].name == "演示服务"
    dialog.close()


def test_mcp_tool_details_parse_json_arguments_before_emitting():
    app()
    panel = ToolDetailsPanel()
    panel.set_tool(
        ToolDefinition(
            id="mcp:mcp-demo:repeat",
            name="重复文本",
            category="MCP",
            description="返回传入文字",
            enabled=True,
            kind="mcp",
            input_schema={"type": "object", "required": ["text"]},
        )
    )
    panel.arguments_input.setPlainText('{"text": "hi"}')
    spy = QSignalSpy(panel.test_requested)

    panel.test_button.click()

    assert spy.count() == 1
    assert spy.at(0)[0] == "mcp:mcp-demo:repeat"
    assert spy.at(0)[1] == {"text": "hi"}
    panel.close()


def test_display_dialog_saves_optional_name_and_description(tmp_path):
    app()
    store = LocalStateStore(tmp_path)
    tool = ToolDefinition(
        id="mcp:mcp-demo:get_forecast",
        name="get_forecast",
        category="MCP",
        description="Get future weather forecast for a location.",
        kind="mcp",
    )
    dialog = MCPToolDisplayDialog(store, tool)
    assert "Get future weather" in dialog.original_description_label.text()
    dialog.display_name_input.setText("天气预报")
    dialog.description_input.setPlainText("查看未来几天的天气。")

    dialog.save_metadata()

    metadata = store.get_mcp_tool_display_metadata("mcp-demo", "get_forecast")
    assert metadata is not None
    assert metadata.display_name == "天气预报"
    assert metadata.description == "查看未来几天的天气。"
    dialog.close()
