from __future__ import annotations

import json
import re
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, Iterator, Literal

from app.models import ChatMessage, SearchHit
from app.services.tool_calling import (
    ToolCallRequest,
    build_planning_messages,
    build_tool_repair_messages,
    build_tool_result_messages,
    normalize_tool_call,
    parse_tool_call,
)
from app.services.tool_contracts import select_candidate_tools, validate_tool_arguments
from app.services.tool_router import CalculatorRouter
from tools.calculator.tool import calculator_tool


@dataclass
class ChatEvent:
    kind: Literal["status", "token", "citation", "tool", "done", "error"]
    payload: Any = None


class ChatService:
    def __init__(self, retrieval, llm_factory, calculator=None, tool_registry=None):
        self.retrieval = retrieval
        self.llm_factory = llm_factory
        self.calculator = calculator or calculator_tool
        self.tool_registry = tool_registry

    def answer(
        self,
        query: str,
        knowledge_base_id: str | Sequence[str],
        model_id: str,
        history: list[ChatMessage],
        knowledge_base_names: dict[str, str] | None = None,
    ) -> Iterator[ChatEvent]:
        invocation = CalculatorRouter.route(query)
        if invocation is not None:
            yield ChatEvent("status", "正在调用计算工具")
            calculation = self.calculator.run(invocation.request)
            yield ChatEvent("tool", {"name": invocation.name, "result": calculation})
            yield ChatEvent("citation", [])
            messages = self._tool_messages(history, query, calculation)
            llm = self.llm_factory(model_id)
            yield ChatEvent("status", "计算完成，正在生成回答")
            for token in llm.generate_stream(messages):
                yield ChatEvent("token", token)
            yield ChatEvent("done", {"citations": [], "tool": calculation})
            return

        yield ChatEvent("status", "正在检索知识库…")
        if isinstance(knowledge_base_id, str):
            hits = self.retrieval.search(knowledge_base_id, query, top_k=5)
        else:
            hits = self.retrieval.search_many(
                knowledge_base_id,
                query,
                top_k=5,
                knowledge_base_names=knowledge_base_names,
            )
            if hits and isinstance(knowledge_base_id, Sequence):
                fallback_id = next((str(item) for item in knowledge_base_id if str(item).strip()), None)
                if fallback_id:
                    hits = [
                        SearchHit(
                            hit.id,
                            hit.text,
                            hit.score,
                            {
                                "knowledge_base_id": fallback_id,
                                **({"knowledge_base_name": knowledge_base_names[fallback_id]} if knowledge_base_names and fallback_id in knowledge_base_names else {}),
                                **hit.metadata,
                            },
                        )
                        if not hit.metadata.get("knowledge_base_id") else hit
                        for hit in hits
                    ]
        citations = [self._citation(hit) for hit in hits]
        yield ChatEvent("citation", citations)
        context = self._context(hits)
        mcp_tools = self._enabled_mcp_tools()
        candidate_tools = select_candidate_tools(query, mcp_tools)
        if self._needs_weather_location_clarification(query, candidate_tools):
            # Do not make the model invent a location or answer from unrelated
            # knowledge-base chunks when the weather request has no city.
            yield ChatEvent("citation", [])
            yield ChatEvent("status", "需要先确认查询地点")
            yield ChatEvent("token", "想查询哪个城市的天气？例如：`上海今天天气怎么样？`")
            yield ChatEvent("done", {"citations": []})
            return
        llm = self.llm_factory(model_id)
        tool_record = None
        if candidate_tools:
            request = self._weather_request(query, candidate_tools)
            if request is None:
                yield ChatEvent("status", "正在判断是否需要本地 MCP 工具…")
                planning_messages = build_planning_messages(history, query, context, candidate_tools)
                planning_text = "".join(
                    llm.generate_stream(planning_messages, max_new_tokens=256)
                )
                request = normalize_tool_call(
                    query,
                    parse_tool_call(planning_text),
                    candidate_tools,
                )
            tool = self._validated_mcp_tool(request, candidate_tools)
            validation_errors = (
                validate_tool_arguments(tool, request.arguments)
                if request is not None and tool is not None
                else ()
            )
            if validation_errors and request is not None and tool is not None:
                yield ChatEvent("status", "正在修复工具参数")
                repair_messages = build_tool_repair_messages(
                    history,
                    query,
                    context,
                    candidate_tools,
                    request,
                    validation_errors,
                )
                repair_text = "".join(
                    llm.generate_stream(repair_messages, max_new_tokens=256)
                )
                request = normalize_tool_call(
                    query,
                    parse_tool_call(repair_text),
                    candidate_tools,
                )
                tool = self._validated_mcp_tool(request, candidate_tools)
                validation_errors = (
                    validate_tool_arguments(tool, request.arguments)
                    if request is not None and tool is not None
                    else ()
                )
            if request is not None and tool is not None and not validation_errors:
                yield ChatEvent("status", f"正在调用 {tool.name} …")
                result = self._call_mcp_tool(request)
                tool_record = {
                    "tool_id": request.tool_id,
                    "name": tool.name,
                    "source": tool.source,
                    "arguments": request.arguments,
                    "result": result,
                }
                yield ChatEvent("tool", tool_record)
                yield ChatEvent("status", "工具调用完成，正在生成最终回答…")
                messages = build_tool_result_messages(
                    history,
                    query,
                    context,
                    request,
                    result,
                )
            else:
                messages = self._messages(history, query, context)
                yield ChatEvent("status", "正在加载本地模型并生成回答…")
        else:
            messages = self._messages(history, query, context)
            yield ChatEvent("status", "正在加载本地模型并生成回答…")
        for token in llm.generate_stream(messages):
            yield ChatEvent("token", token)
        done_payload = {"citations": citations}
        if tool_record is not None:
            done_payload["tool_calls"] = [tool_record]
        yield ChatEvent("done", done_payload)

    def _enabled_mcp_tools(self):
        if self.tool_registry is None:
            return []
        return [
            tool
            for tool in self.tool_registry.list_tools()
            if tool.kind == "mcp" and tool.enabled
        ]

    @classmethod
    def _needs_weather_location_clarification(cls, query: str, candidates) -> bool:
        if (
            not candidates
            or not cls._is_weather_query(query)
            or not any(cls._is_weather_tool(tool) for tool in candidates)
        ):
            return False
        return not cls._location_from_query(query)

    @classmethod
    def _weather_request(cls, query: str, candidates) -> ToolCallRequest | None:
        if not cls._is_weather_query(query):
            return None
        location = cls._location_from_query(query)
        if not location:
            return None
        tool = next((item for item in candidates if cls._is_weather_tool(item)), None)
        properties = dict((tool.input_schema or {}).get("properties", {})) if tool else {}
        if tool is None or "city_name" not in properties:
            return None
        return ToolCallRequest(tool.id, {"city_name": location})

    @staticmethod
    def _is_weather_query(query: str) -> bool:
        text = str(query).casefold()
        return any(
            marker in text
            for marker in (
                "\u5929\u6c14", "\u6c14\u6e29", "\u6e29\u5ea6", "\u9884\u62a5", "\u964d\u96e8", "\u9884\u8b66",
                "weather", "forecast", "temperature", "rain", "snow", "alert",
            )
        )

    @staticmethod
    def _is_weather_tool(tool) -> bool:
        identity = " ".join(
            (
                str(tool.id),
                str(tool.raw_name or ""),
                str(tool.raw_description or ""),
                str(tool.description),
            )
        ).casefold()
        return "weather" in identity or "\u5929\u6c14" in identity

    @staticmethod
    def _location_from_query(query: str) -> str | None:
        text = str(query).casefold()
        common_cities = (
            "\u4e0a\u6d77", "\u5317\u4eac", "\u5e7f\u5dde", "\u6df1\u5733", "\u676d\u5dde", "\u5357\u4eac",
            "\u5929\u6d25", "\u91cd\u5e86", "\u6b66\u6c49", "\u6210\u90fd", "\u897f\u5b89", "\u82cf\u5dde",
            "\u957f\u6c99", "\u9752\u5c9b", "\u53a6\u95e8", "\u53f0\u5317", "\u9999\u6e2f", "\u6fb3\u95e8",
        )
        matched_city = next((city for city in common_cities if city in text), None)
        if matched_city:
            return matched_city
        matched_region = re.search(r"([\u4e00-\u9fff]{2,}(?:\u5e02|\u7701|\u533a|\u53bf|\u5dde|\u56fd))", text)
        if matched_region:
            return matched_region.group(1)
        matched_english = re.search(r"\b(?:in|at)\s+([a-z][a-z .'-]{1,60})\b", text)
        return matched_english.group(1).strip(" .") if matched_english else None

    def _validated_mcp_tool(
        self,
        request: ToolCallRequest | None,
        allowed_tools=None,
    ):
        if request is None or self.tool_registry is None:
            return None
        tool = self.tool_registry.get(request.tool_id)
        if tool is None or tool.kind != "mcp" or not tool.enabled:
            return None
        if allowed_tools is not None and request.tool_id not in {
            item.id for item in allowed_tools
        }:
            return None
        return tool

    def _call_mcp_tool(self, request: ToolCallRequest) -> dict[str, Any]:
        try:
            result = self.tool_registry.call(request.tool_id, request.arguments)
        except Exception as error:
            return {
                "success": False,
                "content": [],
                "structured_content": None,
                "is_error": True,
                "error": str(error),
            }
        if isinstance(result, dict):
            return dict(result)
        return {
            "success": bool(getattr(result, "success", False)),
            "content": list(getattr(result, "content", []) or []),
            "structured_content": getattr(result, "structured_content", None),
            "is_error": bool(getattr(result, "is_error", False)),
            "error": getattr(result, "error", None),
        }

    @staticmethod
    def _citation(hit: SearchHit) -> dict[str, Any]:
        return {
            "id": hit.id,
            "file_name": hit.metadata.get("file_name", hit.metadata.get("source", "未知来源")),
            "page": hit.metadata.get("page"),
            "score": hit.score,
            "text": hit.text,
            "document_id": hit.metadata.get("document_id"),
            "knowledge_base_id": hit.metadata.get("knowledge_base_id"),
            "knowledge_base_name": hit.metadata.get("knowledge_base_name"),
        }

    @staticmethod
    def _context(hits: list[SearchHit]) -> str:
        if not hits:
            return "知识库中没有找到充分依据，请明确告诉用户资料不足，不要编造答案。"
        return "\n\n".join(f"[来源 {index}] {hit.text}" for index, hit in enumerate(hits, start=1))

    @classmethod
    def _messages(cls, history: list[ChatMessage], query: str, context: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": "你是一个本地知识库助手。优先根据给定资料回答；资料不足时明确说明，不要编造。",
            }
        ]
        messages.extend({"role": message.role, "content": message.content} for message in history[-6:])
        messages.append({"role": "user", "content": f"参考资料：\n{context}\n\n问题：{query}"})
        return messages

    @classmethod
    def _tool_messages(cls, history: list[ChatMessage], query: str, calculation: dict[str, Any]) -> list[dict[str, str]]:
        result_text = json.dumps(calculation, ensure_ascii=False)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": "你是本地助手。计算工具已经返回经过程序验证的结果。必须严格使用工具结果回答，不要自行重新计算；如果 success 为 false，要明确告诉用户计算失败原因。",
            }
        ]
        messages.extend({"role": message.role, "content": message.content} for message in history[-6:])
        messages.append({
            "role": "user",
            "content": f"用户问题：{query}\n\n计算工具结果：{result_text}\n\n请用简洁中文回答，并在需要时说明计算结果。",
        })
        return messages
