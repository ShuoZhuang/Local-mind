from app.models import ToolDefinition
from app.services.tool_contracts import (
    contract_for_mcp_tool,
    select_candidate_tools,
    validate_tool_arguments,
)


def tool(name, contract_name=None, description=""):
    identity = contract_name or name
    return ToolDefinition(
        id=f"mcp:test:{name}",
        name=name,
        category="MCP",
        description=description or name,
        enabled=True,
        kind="mcp",
        contract=contract_for_mcp_tool(identity, description or name, {}),
        input_schema={"type": "object"},
    )


def test_candidate_filter_keeps_weather_and_excludes_current_time_for_weather_query():
    weather = tool("get_weather", description="Get weather forecast for a city")
    current_time = tool("get_current_time", description="Get current time in a timezone")

    candidates = select_candidate_tools("上海天气怎么样", [weather, current_time])

    assert [item.name for item in candidates] == ["get_weather"]


def test_weather_contract_selects_current_conditions_instead_of_location_or_status_tools():
    current = tool("get_current_conditions", description="Get current weather conditions for a city")
    forecast = tool("get_forecast", description="Get future weather forecast for a city")
    location = tool("search_location", description="Search locations for weather tools")
    status = tool("check_service_status", description="Check weather service status")

    candidates = select_candidate_tools("上海现在天气怎么样？", [current, forecast, location, status])

    assert [item.name for item in candidates] == ["get_current_conditions"]
    assert status.contract.configured is False


def test_today_weather_prefers_the_weather_summary_tool():
    current = tool("get_current_conditions", description="Get current weather conditions for a city")
    summary = tool("get_weather_summary", description="Get weather summary for a city")

    candidates = select_candidate_tools("\u4eca\u5929\u5929\u6c14\u600e\u4e48\u6837", [current, summary])

    assert [item.name for item in candidates] == ["get_weather_summary"]


def test_validate_tool_arguments_rejects_missing_and_unknown_fields():
    definition = ToolDefinition(
        id="mcp:test:weather",
        name="get_weather",
        category="MCP",
        description="Get weather",
        enabled=True,
        kind="mcp",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
    )

    errors = validate_tool_arguments(definition, {"unexpected": "上海"})

    assert errors == ("missing:city", "unexpected:unexpected")


def test_unknown_mcp_tool_is_not_model_callable_without_a_contract():
    contract = contract_for_mcp_tool("new_unregistered_tool", "Does an unknown operation", {})

    assert contract.configured is False
    assert contract.use_when
    assert contract.avoid_when
