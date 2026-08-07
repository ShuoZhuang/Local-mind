import torch

from app.models import ModelDefinition, SearchHit
from app.services.chat import ChatService, ChatEvent
from app.services.llm import LocalLLM


class FakeRetrieval:
    def __init__(self, hits):
        self.hits = hits

    def search(self, knowledge_base_id, query, top_k=5):
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


def test_local_llm_selects_available_cuda_device(tmp_path):
    llm = LocalLLM(
        ModelDefinition("test", "测试模型", "local-test"),
        tmp_path,
    )

    assert llm.device == ("cuda" if torch.cuda.is_available() else "cpu")
