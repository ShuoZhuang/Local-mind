from __future__ import annotations

import sys
from pathlib import Path

from app.models import MCPServerDefinition
from app.services.chat import ChatService
from app.services.mcp_client import MCPClientService
from app.services.storage import LocalStateStore
from app.services.tool_registry import ToolRegistry
from app.models import ToolDefinition
from tests.test_chat import FakeRetrieval


class PlanningLLM:
    def __init__(self, tool_id: str):
        self.tool_id = tool_id
        self.prompts = []

    def generate_stream(self, messages, max_new_tokens=512):
        self.prompts.append(messages)
        if len(self.prompts) == 1:
            yield (
                '{"tool_call":{"tool_id":"'
                f"{self.tool_id}"
                '","arguments":{"text":"from chat"}}}'
            )
        else:
            yield "工具返回：from chat"


def test_chat_service_calls_real_local_stdio_mcp_server(tmp_path):
    state = LocalStateStore(tmp_path / "state")
    server = MCPServerDefinition.new(
        "本地测试服务",
        sys.executable,
        (str(Path(__file__).with_name("mcp_test_server.py")),),
    )
    state.save_mcp_server(server)
    registry = ToolRegistry(state, MCPClientService())
    registry.refresh_mcp_tools()
    tool_id = next(tool.id for tool in registry.list_tools() if tool.kind == "mcp")
    llm = PlanningLLM(tool_id)
    service = ChatService(
        FakeRetrieval([]),
        lambda model_id: llm,
        tool_registry=registry,
    )

    events = list(service.answer("weather in Shanghai", "kb-ai", "qwen-1.5b", []))

    tool_events = [event for event in events if event.kind == "tool"]
    assert len(tool_events) == 1
    assert tool_events[0].payload["tool_id"] == tool_id
    assert tool_events[0].payload["result"]["structured_content"] == {"text": "from chat"}
    assert "from chat" in llm.prompts[1][-1]["content"]


class WeatherOnlyRegistry:
    def list_tools(self):
        return [
            ToolDefinition(
                id="mcp:weather:get_weather_summary",
                name="天气概览",
                category="MCP",
                description="Get weather summary for a city.",
                enabled=True,
                kind="mcp",
                input_schema={"type": "object", "properties": {"city_name": {"type": "string"}}},
                contract=__import__("app.services.tool_contracts", fromlist=["contract_for_mcp_tool"]).contract_for_mcp_tool(
                    "get_weather_summary", "Get weather summary for a city.", {}
                ),
            )
        ]


class DirectWeatherRegistry(WeatherOnlyRegistry):
    def __init__(self):
        self.request = None
        self._tool = self.list_tools()[0]

    def get(self, tool_id):
        return self._tool if tool_id == self._tool.id else None

    def call(self, tool_id, arguments):
        self.request = (tool_id, arguments)
        return {"success": True, "content": ["Shanghai weather"], "is_error": False}


def test_weather_question_without_a_location_asks_for_city_without_citations():
    service = ChatService(
        FakeRetrieval([]),
        lambda _model_id: (_ for _ in ()).throw(AssertionError("LLM should not be used")),
        tool_registry=WeatherOnlyRegistry(),
    )

    events = list(service.answer("\u4eca\u5929\u5929\u6c14\u600e\u4e48\u6837", "kb-ai", "qwen-1.5b", []))

    assert any(event.kind == "token" and "城市" in event.payload for event in events)
    assert events[-1].payload["citations"] == []


def test_weather_question_with_a_city_calls_the_weather_tool_without_planning_json():
    registry = DirectWeatherRegistry()
    service = ChatService(
        FakeRetrieval([]),
        lambda _model_id: PlanningLLM("unused"),
        tool_registry=registry,
    )

    events = list(service.answer("\u4e0a\u6d77\u4eca\u5929\u5929\u6c14\u600e\u4e48\u6837", "kb-ai", "qwen-1.5b", []))

    assert registry.request == ("mcp:weather:get_weather_summary", {"city_name": "\u4e0a\u6d77"})
    assert any(event.kind == "tool" for event in events)
