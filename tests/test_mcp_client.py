from __future__ import annotations

import sys
from pathlib import Path

from app.models import MCPServerDefinition
from app.services.mcp_client import MCPClientService


def local_test_server() -> MCPServerDefinition:
    return MCPServerDefinition.new(
        "本地测试服务",
        sys.executable,
        (str(Path(__file__).with_name("mcp_test_server.py")),),
    )


def test_client_discovers_tools_from_local_stdio_server():
    tools = MCPClientService().discover(local_test_server())

    assert [tool.name for tool in tools] == ["repeat"]
    assert tools[0].description == "返回传入的文字。"
    assert tools[0].input_schema["required"] == ["text"]


def test_client_calls_tool_and_keeps_structured_result():
    result = MCPClientService().call_tool(
        local_test_server(),
        "repeat",
        {"text": "LocalMind"},
    )

    assert result.success is True
    assert result.structured_content == {"text": "LocalMind"}
    assert any("LocalMind" in item for item in result.content)


def test_client_returns_readable_error_when_command_is_missing():
    server = MCPServerDefinition.new("不存在", "missing-mcp-command")

    result = MCPClientService().call_tool(server, "repeat", {"text": "x"})

    assert result.success is False
    assert "missing-mcp-command" in result.error
