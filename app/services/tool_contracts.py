from __future__ import annotations

import re
from typing import Any, Sequence

from app.models import ToolContract, ToolDefinition


def contract_for_mcp_tool(
    name: str,
    description: str,
    input_schema: dict[str, Any] | None,
) -> ToolContract:
    """Return an explicit contract for known MCP tools.

    Unknown tools remain visible in the tool center, but are deliberately not
    model-callable until a maintainer adds a contract here.
    """
    identity = f"{name} {description}".casefold()
    tool_name = name.casefold().strip()
    # These two server-internal helpers should remain visible in the tool
    # center, but are not safe first-choice answers for a normal weather ask.
    if tool_name in {"check_service_status", "search_location"}:
        return ToolContract(
            purpose="MCP server internal helper.",
            use_when=("Only use from a dedicated multi-step weather workflow.",),
            avoid_when=("Do not select for direct user questions.",),
            recovery_hint="Use a weather query tool that accepts a city instead.",
            configured=False,
        )
    if tool_name == "get_current_conditions":
        return ToolContract(
            purpose="Query current weather observations for a named location.",
            use_when=("The user asks about weather right now, current temperature, or current conditions.",),
            avoid_when=("The user asks for a future forecast, weather alerts, or time conversion.",),
            intent_keywords=("天气", "现在", "当前", "实时", "气温", "温度", "weather", "current conditions"),
            intent_exclusions=("明天", "预报", "forecast", "预警", "alert"),
            parameter_rules=("Provide city_name or location_name; never use a timezone as the city.",),
            examples=("上海现在天气怎么样？", "What is the current weather in Shanghai?"),
            recovery_hint="Ask for the city when the location is missing.",
            retry_on_error=True,
        )
    if tool_name == "get_forecast":
        return ToolContract(
            purpose="Query a future weather forecast for a named location.",
            use_when=("The user asks about tomorrow, this week, or a future forecast.",),
            avoid_when=("The user asks only for current conditions or weather alerts.",),
            intent_keywords=("明天", "未来", "预报", "forecast", "tomorrow", "next week"),
            intent_exclusions=("现在", "当前", "实时", "alert", "预警"),
            parameter_rules=("Provide city_name or location_name; include a forecast period only when requested.",),
            examples=("上海明天天气怎么样？",),
            recovery_hint="Ask for the city when the location is missing.",
            retry_on_error=True,
        )
    if tool_name == "get_alerts":
        return ToolContract(
            purpose="Query active weather alerts for a named location.",
            use_when=("The user explicitly asks for weather warnings, alerts, or safety notices.",),
            avoid_when=("The user asks for a normal forecast or current temperature.",),
            intent_keywords=("预警", "警报", "alert", "warning"),
            intent_exclusions=("现在", "当前", "温度", "forecast"),
            parameter_rules=("Provide city_name or location_name.",),
            examples=("上海有天气预警吗？",),
            recovery_hint="Ask for the city when the location is missing.",
            retry_on_error=True,
        )
    if tool_name == "get_weather_summary":
        return ToolContract(
            purpose="Give a broad weather overview for a named location.",
            use_when=("The user asks for a general weather overview without asking for a specific forecast or alert.",),
            avoid_when=("The user clearly asks for current observations, a future forecast, or alerts.",),
            intent_keywords=("天气", "今天", "weather"),
            intent_exclusions=("现在", "当前", "实时", "明天", "未来", "预报", "forecast", "预警", "alert"),
            parameter_rules=("Provide city_name or location_name.",),
            examples=("上海天气怎么样？",),
            recovery_hint="Ask for the city when the location is missing.",
            retry_on_error=True,
        )
    if "get_current_time" in identity or "current time" in identity:
        return ToolContract(
            purpose="查询指定 IANA 时区的当前时间。",
            use_when=("用户询问现在几点、当前时间或某地当前时间。",),
            avoid_when=("用户要把一个已知时间转换到另一个时区。",),
            intent_keywords=("几点", "几时", "当前时间", "现在时间", "current time", "what time"),
            intent_exclusions=("转换", "换算", "convert", "timezone conversion"),
            parameter_rules=("timezone 必须是有效的 IANA 时区，例如 Asia/Shanghai。",),
            examples=("上海几点了", "What time is it in Tokyo?"),
            recovery_hint="如果 timezone 缺失，使用用户明确提到的地点；没有地点时使用 Asia/Shanghai。",
            retry_on_error=True,
        )
    if "convert_time" in identity or "time conversion" in identity:
        return ToolContract(
            purpose="把一个已知时间从源时区转换到目标时区。",
            use_when=("用户明确提供了时间，并要求在两个时区之间转换。",),
            avoid_when=("用户只是询问当前几点，或没有提供源时区和具体时间。",),
            intent_keywords=("转换时间", "时区转换", "convert time", "timezone conversion", "换算时区"),
            intent_exclusions=("几点", "现在", "当前时间", "what time", "current time"),
            parameter_rules=(
                "source_timezone、time、target_timezone 三个参数都必填。",
                "source_timezone 和 target_timezone 必须是 IANA 时区。",
            ),
            examples=("把 14:40 从 Asia/Tokyo 转换成 Asia/Shanghai",),
            recovery_hint="缺少任一参数时不要猜测，改为向用户询问缺失信息。",
        )
    if any(marker in identity for marker in ("weather", "forecast", "天气", "气温")):
        return ToolContract(
            purpose="查询指定地点的天气或天气预报。",
            use_when=("用户询问某地天气、温度、降雨或天气预报。",),
            avoid_when=("用户询问当前时间、日历安排或历史天气。",),
            intent_keywords=("天气", "气温", "温度", "降雨", "预报", "weather", "forecast", "temperature"),
            intent_exclusions=("时间", "几点", "calendar"),
            parameter_rules=("地点或城市参数必填，不能把时区当作城市。",),
            examples=("上海今天的天气怎么样", "What is the weather in Shanghai?"),
            recovery_hint="缺少地点时向用户询问城市，不要默认调用。",
            retry_on_error=True,
        )
    if any(marker in identity for marker in ("vlr", "valorant", "match schedule", "比赛日程")):
        return ToolContract(
            purpose="从 VLR 查询 Valorant 比赛日程。",
            use_when=("用户询问 Valorant、VLR 或电竞比赛赛程。",),
            avoid_when=("用户询问普通日历、天气或时间。",),
            intent_keywords=("vlr", "valorant", "比赛日程", "赛程", "电竞比赛", "match schedule"),
            intent_exclusions=("天气", "weather", "几点", "calendar"),
            parameter_rules=("赛事、日期和队伍过滤条件必须符合 MCP 工具 schema。",),
            examples=("VLR 今天有哪些 Valorant 比赛",),
            recovery_hint="查询失败时说明 VLR 服务不可用，不要编造比赛。",
            retry_on_error=True,
        )
    if any(marker in identity for marker in ("calendar", "date", "日历", "日期")):
        return ToolContract(
            purpose="查询日历日期或日历时间信息。",
            use_when=("用户询问日期、星期或日历信息。",),
            avoid_when=("用户询问天气、Valorant 赛程或时区转换。",),
            intent_keywords=("日历", "日期", "星期", "calendar", "date"),
            intent_exclusions=("天气", "weather", "vlr", "valorant"),
            parameter_rules=("日期或时区参数必须遵循工具 schema。",),
            examples=("今天是几月几号", "What day is it?"),
            recovery_hint="缺少目标日期或时区时使用工具支持的默认值，否则向用户询问。",
            retry_on_error=True,
        )
    return ToolContract(
        purpose="该 MCP 工具尚未配置 LocalMind 的调用边界。",
        use_when=("仅在补充了明确的工具契约后使用。",),
        avoid_when=("在契约未配置时禁止让模型调用。",),
        recovery_hint="请先在 contract_for_mcp_tool 中为该工具添加用途、参数和示例。",
        configured=False,
    )


def select_candidate_tools(
    query: str,
    tools: Sequence[ToolDefinition],
) -> list[ToolDefinition]:
    """Reduce the model's tool choices to contract-matching candidates."""
    text = str(query).casefold()
    active = [
        tool
        for tool in tools
        if tool.enabled and tool.kind == "mcp" and tool.contract.configured
    ]
    scored: list[tuple[int, str, ToolDefinition]] = []
    for tool in active:
        if any(term.casefold() in text for term in tool.contract.intent_exclusions):
            continue
        score = sum(1 for term in tool.contract.intent_keywords if term.casefold() in text)
        if score:
            scored.append((score, tool.id, tool))
    if scored:
        scored.sort(key=lambda item: (-item[0], item[1]))
        best_score = scored[0][0]
        return [item[2] for item in scored if item[0] == best_score]
    return [tool for tool in active if not tool.contract.intent_keywords]


def validate_tool_arguments(
    tool: ToolDefinition,
    arguments: dict[str, Any],
) -> tuple[str, ...]:
    """Validate the small JSON-schema subset used by MCP tools."""
    schema = dict(tool.input_schema or {})
    if isinstance(schema.get("parameters"), dict):
        schema = dict(schema["parameters"])
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    errors: list[str] = []
    for name in schema.get("required", []) or []:
        if name not in arguments or arguments[name] in (None, ""):
            errors.append(f"missing:{name}")
    if schema.get("additionalProperties") is False:
        for name in arguments:
            if name not in properties:
                errors.append(f"unexpected:{name}")
    for name, value in arguments.items():
        definition = properties.get(name)
        if not isinstance(definition, dict) or value is None:
            continue
        expected = definition.get("type")
        if expected == "string" and not isinstance(value, str):
            errors.append(f"type:{name}:string")
        elif expected == "object" and not isinstance(value, dict):
            errors.append(f"type:{name}:object")
        elif expected == "array" and not isinstance(value, list):
            errors.append(f"type:{name}:array")
        elif expected == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            errors.append(f"type:{name}:number")
        elif expected == "boolean" and not isinstance(value, bool):
            errors.append(f"type:{name}:boolean")
    return tuple(errors)
