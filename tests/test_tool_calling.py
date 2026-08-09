from app.models import ToolDefinition
from app.services.tool_calling import (
    ToolCallRequest,
    build_planning_messages,
    build_tool_catalog,
    build_tool_result_messages,
    normalize_tool_call,
    parse_tool_call,
)


def mcp_tool():
    return ToolDefinition(
        id="mcp:weather:weather",
        name="天气查询",
        category="MCP",
        description="查询城市天气",
        capabilities=("MCP",),
        enabled=True,
        kind="mcp",
        source="天气服务",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )


def current_time_tool():
    return ToolDefinition(
        id="mcp:time:get_current_time",
        name="get_current_time",
        category="MCP",
        description="Get current time in a specific timezone",
        capabilities=("MCP",),
        enabled=True,
        kind="mcp",
        source="time",
        input_schema={"type": "object", "required": ["timezone"]},
    )


def convert_time_tool():
    return ToolDefinition(
        id="mcp:time:convert_time",
        name="convert_time",
        category="MCP",
        description="Convert time between timezones",
        capabilities=("MCP",),
        enabled=True,
        kind="mcp",
        source="time",
        input_schema={
            "type": "object",
            "required": ["source_timezone", "time", "target_timezone"],
        },
    )


def test_catalog_contains_only_enabled_mcp_details():
    disabled = ToolDefinition(
        id="mcp:disabled:run",
        name="Disabled",
        category="MCP",
        description="should not be offered",
        enabled=False,
        kind="mcp",
    )
    local = ToolDefinition(
        id="calculator",
        name="Calculator",
        category="计算",
        description="local calculator",
        enabled=True,
        kind="tool",
    )

    catalog = build_tool_catalog([mcp_tool(), disabled, local])

    assert "mcp:weather:weather" in catalog
    assert "查询城市天气" in catalog
    assert '"city"' in catalog
    assert "mcp:disabled:run" not in catalog
    assert "calculator" not in catalog


def test_parse_tool_call_accepts_plain_and_fenced_json():
    expected = ToolCallRequest("mcp:weather:weather", {"city": "上海"})

    assert parse_tool_call(
        '{"tool_call":{"tool_id":"mcp:weather:weather","arguments":{"city":"上海"}}}'
    ) == expected
    assert parse_tool_call(
        '```json\n{"tool_call":{"tool_id":"mcp:weather:weather","arguments":{"city":"上海"}}}\n```'
    ) == expected


def test_parse_tool_call_returns_none_for_no_call_or_invalid_payload():
    assert parse_tool_call('{"tool_call":null}') is None
    assert parse_tool_call('{"tool_call":{"tool_id":"x","arguments":[]}}') is None
    assert parse_tool_call('{"tool_call":{"tool_id":"","arguments":{}}}') is None
    assert parse_tool_call("not json") is None


def test_prompts_include_query_context_and_tool_result():
    planning = build_planning_messages(
        [],
        "上海天气如何",
        "无检索资料",
        [mcp_tool()],
    )
    assert "上海天气如何" in planning[-1]["content"]
    assert "mcp:weather:weather" in planning[-1]["content"]

    final = build_tool_result_messages(
        [],
        "上海天气如何",
        "无检索资料",
        ToolCallRequest("mcp:weather:weather", {"city": "上海"}),
        {"success": True, "temperature": 28},
    )
    assert "temperature" in final[-1]["content"]
    assert "上海天气如何" in final[-1]["content"]


def test_normalize_tool_call_uses_current_time_tool_for_chinese_time_queries():
    request = ToolCallRequest(
        "mcp:time:convert_time",
        {"source_timezone": "", "time": "14:40:55", "target_timezone": "Asia/Shanghai"},
    )

    normalized = normalize_tool_call(
        "上海几点了",
        request,
        [convert_time_tool(), current_time_tool()],
    )

    assert normalized == ToolCallRequest(
        "mcp:time:get_current_time",
        {"timezone": "Asia/Shanghai"},
    )


def test_normalize_tool_call_defaults_plain_time_query_to_shanghai():
    normalized = normalize_tool_call(
        "现在几点了",
        None,
        [current_time_tool()],
    )

    assert normalized == ToolCallRequest(
        "mcp:time:get_current_time",
        {"timezone": "Asia/Shanghai"},
    )
