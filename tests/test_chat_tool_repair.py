from app.services.chat import ChatService
from tests.test_chat import FakeRetrieval, FakeToolRegistry


class RepairingPlanningLLM:
    def __init__(self):
        self.prompts = []

    def generate_stream(self, messages, max_new_tokens=512):
        self.prompts.append(messages)
        if len(self.prompts) == 1:
            yield '{"tool_call":{"tool_id":"mcp:weather:weather","arguments":{}}}'
        elif len(self.prompts) == 2:
            yield '{"tool_call":{"tool_id":"mcp:weather:weather","arguments":{"city":"Shanghai"}}}'
        else:
            yield "Weather result"


def test_chat_service_repairs_known_tool_call_with_missing_required_argument():
    registry = FakeToolRegistry()
    llm = RepairingPlanningLLM()
    service = ChatService(
        FakeRetrieval([]),
        lambda model_id: llm,
        tool_registry=registry,
    )

    events = list(service.answer("weather in Shanghai", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == [("mcp:weather:weather", {"city": "Shanghai"})]
    assert len([event for event in events if event.kind == "tool"]) == 1
    assert len(llm.prompts) == 3
