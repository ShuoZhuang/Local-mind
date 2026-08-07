from __future__ import annotations

import json
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, Iterator, Literal

from app.models import ChatMessage, SearchHit
from app.services.tool_router import CalculatorRouter
from tools.calculator.tool import calculator_tool


@dataclass
class ChatEvent:
    kind: Literal["status", "token", "citation", "tool", "done", "error"]
    payload: Any = None


class ChatService:
    def __init__(self, retrieval, llm_factory, calculator=None):
        self.retrieval = retrieval
        self.llm_factory = llm_factory
        self.calculator = calculator or calculator_tool

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
        messages = self._messages(history, query, context)
        llm = self.llm_factory(model_id)
        yield ChatEvent("status", "正在加载本地模型并生成回答…")
        for token in llm.generate_stream(messages):
            yield ChatEvent("token", token)
        yield ChatEvent("done", {"citations": citations})

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
