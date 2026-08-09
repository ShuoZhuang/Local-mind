from app.models import MCPServerDefinition, MCPToolDisplayMetadata
from app.services.mcp_client import MCPCallResult, MCPToolInfo
from app.services.storage import LocalStateStore
from app.services.tool_registry import ToolRegistry


class FakeMCPClient:
    def __init__(self, tool_name="repeat"):
        self.tool_name = tool_name
        self.discover_calls = []
        self.call_requests = []

    def discover(self, server):
        self.discover_calls.append(server.id)
        return [
            MCPToolInfo(
                name=self.tool_name,
                title="重复文本",
                description="返回传入的文字。",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        ]

    def call_tool(self, server, tool_name, arguments):
        self.call_requests.append((server.id, tool_name, arguments))
        return MCPCallResult(True, [arguments["text"]], {"text": arguments["text"]})


def test_registry_combines_calculator_and_discovered_mcp_tools(tmp_path):
    store = LocalStateStore(tmp_path)
    server = MCPServerDefinition.new("演示服务", "python")
    store.save_mcp_server(server)
    registry = ToolRegistry(store, FakeMCPClient())

    registry.refresh_mcp_tools()

    tools = registry.list_tools()
    assert [tool.id for tool in tools] == ["calculator", f"mcp:{server.id}:repeat"]
    assert tools[1].kind == "mcp"
    assert tools[1].source == "演示服务"
    assert tools[1].input_schema["required"] == ["text"]


def test_registry_ignores_disabled_server_and_routes_mcp_call(tmp_path):
    store = LocalStateStore(tmp_path)
    enabled = MCPServerDefinition.new("可用服务", "python")
    disabled = MCPServerDefinition.new("关闭服务", "python", enabled=False)
    store.save_mcp_server(enabled)
    store.save_mcp_server(disabled)
    client = FakeMCPClient(tool_name="get_weather")
    registry = ToolRegistry(store, client)

    registry.refresh_mcp_tools()
    result = registry.call(f"mcp:{enabled.id}:get_weather", {"text": "LocalMind"})

    assert client.discover_calls == [enabled.id]
    assert client.call_requests == [(enabled.id, "get_weather", {"text": "LocalMind"})]
    assert result.structured_content == {"text": "LocalMind"}


def test_registry_hydrates_enabled_mcp_tools_from_snapshot_without_discovery(tmp_path):
    store = LocalStateStore(tmp_path)
    server = MCPServerDefinition.new("天气", "npx")
    store.save_mcp_server(server)
    store.save_mcp_tool_snapshot([
        {
            "server_id": server.id,
            "tool_name": "get_forecast",
            "title": "get_forecast",
            "description": "Get future weather forecast for a location.",
            "input_schema": {"type": "object"},
        }
    ])
    client = FakeMCPClient(tool_name="get_forecast")

    registry = ToolRegistry(store, client)

    tool = registry.get(f"mcp:{server.id}:get_forecast")
    assert client.discover_calls == []
    assert tool is not None
    assert tool.description == "Get future weather forecast for a location."


def test_registry_uses_saved_display_override_after_snapshot_hydration(tmp_path):
    store = LocalStateStore(tmp_path)
    server = MCPServerDefinition.new("天气", "npx")
    store.save_mcp_server(server)
    store.save_mcp_tool_snapshot([
        {
            "server_id": server.id,
            "tool_name": "get_forecast",
            "title": "get_forecast",
            "description": "Get future weather forecast for a location.",
            "input_schema": {"type": "object"},
        }
    ])
    store.save_mcp_tool_display_metadata(
        MCPToolDisplayMetadata(server.id, "get_forecast", "天气预报", "查看指定城市未来天气。")
    )

    tool = ToolRegistry(store, FakeMCPClient(tool_name="get_forecast")).get(
        f"mcp:{server.id}:get_forecast"
    )

    assert tool is not None
    assert tool.name == "天气预报"
    assert tool.description == "查看指定城市未来天气。"
