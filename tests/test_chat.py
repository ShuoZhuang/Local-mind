import torch

from app.models import ModelDefinition, SearchHit, ToolDefinition
from app.services.chat import ChatService, ChatEvent
from app.services.llm import LocalLLM
from app.services.mcp_client import MCPCallResult


class FakeRetrieval:
    def __init__(self, hits):
        self.hits = hits

    def search(self, knowledge_base_id, query, top_k=5):
        return self.hits[:top_k]

    def search_many(self, knowledge_base_ids, query, top_k=5, knowledge_base_names=None):
        return self.hits[:top_k]


class FakeLLM:
    def __init__(self):
        self.prompts = []

    def generate_stream(self, messages, max_new_tokens=512):
        self.prompts.append(messages)
        yield "这是"
        yield "根据资料的回答。"


class FakeCalculator:
    def __init__(self):
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return {
            "success": True,
            "mode": "arithmetic",
            "expression": request["expression"],
            "result": "121932631112635269",
            "steps": [],
            "error": None,
        }


class FakeToolRegistry:
    def __init__(self, result=None):
        self.calls = []
        self.tool = ToolDefinition(
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
                "additionalProperties": False,
            },
        )
        self.result = result or MCPCallResult(
            True,
            ["28 度"],
            {"temperature": 28},
        )

    def list_tools(self):
        return [self.tool]

    def get(self, tool_id):
        return self.tool if tool_id == self.tool.id else None

    def call(self, tool_id, arguments):
        self.calls.append((tool_id, arguments))
        return self.result


class PlanningLLM(FakeLLM):
    def __init__(self, planning_text):
        super().__init__()
        self.planning_text = planning_text

    def generate_stream(self, messages, max_new_tokens=512):
        self.prompts.append(messages)
        if len(self.prompts) == 1:
            yield self.planning_text
        else:
            yield "天气是 28 度。"


def test_chat_service_includes_sources_and_question_in_prompt():
    retrieval = FakeRetrieval([
        SearchHit("chunk-1", "Embedding 可以把文本转换成向量。", 0.91, {"file_name": "embedding.md"})
    ])
    llm = FakeLLM()
    service = ChatService(retrieval, lambda model_id: llm)

    events = list(service.answer("什么是 Embedding？", "kb-ai", "qwen-1.5b", []))

    assert [event.kind for event in events] == [
        "status", "citation", "status", "token", "token", "done"
    ]
    prompt = llm.prompts[0]
    assert "什么是 Embedding？" in prompt[-1]["content"]
    assert "Embedding 可以把文本转换成向量" in prompt[-1]["content"]
    assert events[1].payload[0]["file_name"] == "embedding.md"


def test_chat_service_accepts_multiple_knowledge_bases_and_cites_the_selected_one():
    hit = SearchHit("chunk-1", "资料内容", 0.91, {"file_name": "notes.md"})
    retrieval = FakeRetrieval([hit])
    llm = FakeLLM()
    service = ChatService(retrieval, lambda model_id: llm)

    events = list(service.answer(
        "问题",
        ["kb-ai", "kb-rag"],
        "qwen-1.5b",
        [],
        knowledge_base_names={"kb-ai": "AI 笔记", "kb-rag": "RAG 笔记"},
    ))

    assert events[1].payload[0]["knowledge_base_id"] in {"kb-ai", "kb-rag"}
    assert events[1].payload[0]["knowledge_base_name"] in {"AI 笔记", "RAG 笔记"}


def test_chat_service_marks_missing_context_in_prompt():
    retrieval = FakeRetrieval([])
    llm = FakeLLM()
    service = ChatService(retrieval, lambda model_id: llm)

    list(service.answer("一个没有资料的问题", "kb-empty", "qwen-1.5b", []))

    assert "没有找到充分依据" in llm.prompts[0][-1]["content"]


def test_chat_service_uses_calculator_before_retrieval():
    retrieval = FakeRetrieval([])
    llm = FakeLLM()
    calculator = FakeCalculator()
    service = ChatService(retrieval, lambda model_id: llm, calculator)

    events = list(service.answer("请计算 123456789 × 987654321", "kb-ai", "qwen-1.5b", []))

    assert calculator.requests == [
        {"mode": "arithmetic", "expression": "123456789*987654321"}
    ]
    assert [event.kind for event in events] == [
        "status", "tool", "citation", "status", "token", "token", "done"
    ]
    assert events[1].payload["name"] == "calculator"
    assert events[2].payload == []
    assert "121932631112635269" in llm.prompts[0][-1]["content"]


def test_chat_service_calls_enabled_mcp_tool_and_uses_result_in_final_prompt():
    registry = FakeToolRegistry()
    llm = PlanningLLM(
        '{"tool_call":{"tool_id":"mcp:weather:weather","arguments":{"city":"上海"}}}'
    )
    service = ChatService(
        FakeRetrieval([]),
        lambda model_id: llm,
        tool_registry=registry,
    )

    events = list(service.answer("上海天气如何", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == [("mcp:weather:weather", {"city": "上海"})]
    assert [event.kind for event in events] == [
        "status",
        "citation",
        "status",
        "status",
        "tool",
        "status",
        "token",
        "done",
    ]
    assert events[4].payload["tool_id"] == "mcp:weather:weather"
    assert events[4].payload["result"]["structured_content"] == {"temperature": 28}
    assert "temperature" in llm.prompts[1][-1]["content"]


def test_chat_service_skips_mcp_when_model_returns_null_call():
    registry = FakeToolRegistry()
    llm = PlanningLLM('{"tool_call":null}')
    service = ChatService(
        FakeRetrieval([]),
        lambda model_id: llm,
        tool_registry=registry,
    )

    events = list(service.answer("你好", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == []
    assert not any(event.kind == "tool" for event in events)
    assert len(llm.prompts) == 2


def test_chat_service_rejects_unknown_mcp_tool_without_calling_registry():
    registry = FakeToolRegistry()
    llm = PlanningLLM(
        '{"tool_call":{"tool_id":"mcp:unknown:run","arguments":{}}}'
    )
    service = ChatService(
        FakeRetrieval([]),
        lambda model_id: llm,
        tool_registry=registry,
    )

    events = list(service.answer("运行未知工具", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == []
    assert not any(event.kind == "tool" for event in events)
    assert len(llm.prompts) == 2


def test_chat_service_preserves_calculator_shortcut_with_registry():
    registry = FakeToolRegistry()
    llm = FakeLLM()
    calculator = FakeCalculator()
    service = ChatService(
        FakeRetrieval([]),
        lambda model_id: llm,
        calculator,
        registry,
    )

    list(service.answer("计算 123 + 456", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == []
    assert len(llm.prompts) == 1


def test_local_llm_selects_available_cuda_device(tmp_path):
    llm = LocalLLM(
        ModelDefinition("test", "测试模型", "local-test"),
        tmp_path,
    )

    assert llm.device == ("cuda" if torch.cuda.is_available() else "cpu")
