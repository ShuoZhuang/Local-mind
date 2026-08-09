from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.models import ChatMessage, ToolDefinition


@dataclass(frozen=True)
class ToolCallRequest:
    tool_id: str
    arguments: dict[str, Any]


def build_tool_catalog(tools: Sequence[ToolDefinition]) -> str:
    catalog = []
    for tool in tools:
        if tool.kind != "mcp" or not tool.enabled or not tool.contract.configured:
            continue
        catalog.append(
            {
                "tool_id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "contract": tool.contract.to_dict(),
            }
        )
    return json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))


def build_planning_messages(
    history: Sequence[ChatMessage],
    query: str,
    context: str,
    tools: Sequence[ToolDefinition],
) -> list[dict[str, str]]:
    system = (
        "你是 LocalMind 的工具规划器。只判断当前问题是否需要调用一个已提供的本地 MCP 工具。"
        "必须只输出一个 JSON 对象，不要输出解释、Markdown 或其他文字。"
        '不调用时输出 {"tool_call":null}；调用时输出 '
        '{"tool_call":{"tool_id":"工具 ID","arguments":{}}}。'
        "arguments 必须是 JSON 对象，不能编造工具目录之外的工具。"
        "如果用户询问现在几点、当前时间或某地时间，优先选择名称为 get_current_time 的工具，"
        "并且必须填写 timezone；不要把当前时间问题交给 convert_time。"
        "只有用户明确要求在两个时区之间转换时，才选择 convert_time，并完整填写 source_timezone、time、target_timezone。"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(
        {"role": message.role, "content": message.content}
        for message in history[-6:]
    )
    messages.append(
        {
            "role": "user",
            "content": (
                f"可用 MCP 工具目录：\n{build_tool_catalog(tools)}\n\n"
                f"知识库参考资料：\n{context}\n\n用户问题：\n{query}"
            ),
        }
    )
    return messages


def build_tool_repair_messages(
    history: Sequence[ChatMessage],
    query: str,
    context: str,
    tools: Sequence[ToolDefinition],
    request: ToolCallRequest,
    errors: Sequence[str],
) -> list[dict[str, str]]:
    system = (
        "You repair a LocalMind MCP tool call. Return JSON only. "
        "Use only a tool from the provided catalog and obey its contract. "
        "If the request cannot be repaired without guessing, return "
        '{"tool_call":null}.'
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(
        {"role": message.role, "content": message.content}
        for message in history[-6:]
    )
    messages.append(
        {
            "role": "user",
            "content": (
                f"Tool catalog:\n{build_tool_catalog(tools)}\n\n"
                f"Knowledge context:\n{context}\n\n"
                f"User query:\n{query}\n\n"
                f"Invalid tool call:\n{json.dumps({'tool_id': request.tool_id, 'arguments': request.arguments}, ensure_ascii=False)}\n"
                f"Validation errors:\n{json.dumps(list(errors), ensure_ascii=False)}\n"
                "Repair the call once, without inventing missing facts."
            ),
        }
    )
    return messages


_TIME_QUERY_MARKERS = (
    "几点",
    "几时",
    "当前时间",
    "现在时间",
    "目前时间",
    "北京时间",
    "what time",
    "current time",
)

_TIMEZONE_BY_PLACE = (
    ("上海", "Asia/Shanghai"),
    ("北京", "Asia/Shanghai"),
    ("中国", "Asia/Shanghai"),
    ("北京时间", "Asia/Shanghai"),
    ("香港", "Asia/Hong_Kong"),
    ("澳门", "Asia/Macau"),
    ("台北", "Asia/Taipei"),
    ("东京", "Asia/Tokyo"),
    ("日本", "Asia/Tokyo"),
    ("伦敦", "Europe/London"),
    ("纽约", "America/New_York"),
    ("洛杉矶", "America/Los_Angeles"),
    ("悉尼", "Australia/Sydney"),
)


def normalize_tool_call(
    query: str,
    request: ToolCallRequest | None,
    tools: Sequence[ToolDefinition],
) -> ToolCallRequest | None:
    """Repair the common current-time routing mistake before MCP is called."""
    query_text = str(query).casefold()
    if not any(marker.casefold() in query_text for marker in _TIME_QUERY_MARKERS):
        return request

    current_time_tool = next(
        (
            tool
            for tool in tools
            if tool.enabled
            and tool.kind == "mcp"
            and _looks_like_current_time_tool(tool)
        ),
        None,
    )
    if current_time_tool is None:
        return request

    # “几点了” is a current-time lookup, not a conversion. Use the user's
    # named place when it is one of the common IANA mappings; Chinese queries
    # without a place default to the user's local timezone in this app.
    return ToolCallRequest(
        current_time_tool.id,
        {"timezone": _timezone_for_query(query_text)},
    )


def _looks_like_current_time_tool(tool: ToolDefinition) -> bool:
    signature = " ".join((tool.id, tool.name, tool.description)).casefold()
    return "get_current_time" in signature or (
        "current time" in signature and "convert" not in signature
    )


def _timezone_for_query(query: str) -> str:
    for place, timezone in _TIMEZONE_BY_PLACE:
        if place.casefold() in query:
            return timezone
    return "Asia/Shanghai"


def parse_tool_call(text: str) -> ToolCallRequest | None:
    candidate = str(text).strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        payload = json.loads(candidate)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    tool_call = payload.get("tool_call")
    if not isinstance(tool_call, dict):
        return None
    tool_id = tool_call.get("tool_id")
    arguments = tool_call.get("arguments", {})
    if not isinstance(tool_id, str) or not tool_id.strip():
        return None
    if not isinstance(arguments, dict):
        return None
    return ToolCallRequest(tool_id.strip(), dict(arguments))


def build_tool_result_messages(
    history: Sequence[ChatMessage],
    query: str,
    context: str,
    request: ToolCallRequest,
    result: dict[str, Any],
) -> list[dict[str, str]]:
    system = (
        "你是 LocalMind 的本地知识助手。工具结果是唯一可信的工具事实，"
        "请结合知识库资料和工具结果回答用户。不要声称工具没有调用，"
        "结果不足时要明确说明，最终回答使用清晰的 Markdown。"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(
        {"role": message.role, "content": message.content}
        for message in history[-6:]
    )
    result_text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    messages.append(
        {
            "role": "user",
            "content": (
                f"知识库参考资料：\n{context}\n\n"
                f"用户问题：\n{query}\n\n"
                f"已调用工具：\n{request.tool_id}\n"
                f"工具参数：\n{json.dumps(request.arguments, ensure_ascii=False)}\n\n"
                f"工具结果：\n{result_text}"
            ),
        }
    )
    return messages
