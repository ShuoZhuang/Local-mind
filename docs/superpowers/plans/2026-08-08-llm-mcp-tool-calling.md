# LocalMind LLM MCP Tool Calling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让本地 LLM 能选择并调用已经启用的本地 stdio MCP Tool，然后基于工具结果生成最终回答。

**Architecture:** 在现有 `ToolRegistry` 之上增加一个纯逻辑的工具调用协议模块。`ChatService` 先检索知识库并执行一次规划生成，解析模型输出的 JSON 请求，经过注册表校验后调用 MCP，再进行一次最终流式生成。Qt 主线程只负责把共享注册表注入服务和展示已有 `tool` 事件，MCP 调用继续运行在 `StreamWorker` 所在线程。

**Tech Stack:** Python 3.10、PySide6、pytest、现有 Transformers 本地 LLM、官方 `mcp` Python SDK、现有 `ToolRegistry`/`MCPClientService`。

## Global Constraints

- 只调用本机配置的 `stdio` MCP Server，不加入远程 HTTP/SSE MCP。
- 只允许调用 `ToolRegistry` 中已经发现且启用的 MCP Tool。
- 每次用户请求最多执行一次 MCP Tool。
- 保留现有计算器优先路由和知识库检索逻辑。
- 模型只能提出工具 ID 和 JSON 参数，实际执行必须经过注册表校验。
- 工具失败要回传模型并生成可读回答，不把异常直接抛到 UI。
- 不执行模型生成的任意命令，不把 Server 启动命令或环境变量写入聊天记录。

---

### Task 1: Add the pure MCP planning protocol

**Files:**
- Create: `app/services/tool_calling.py`
- Create: `tests/test_tool_calling.py`

**Interfaces:**
- Consumes: `ToolDefinition` objects from `app.models` and JSON-serializable MCP results.
- Produces: `ToolCallRequest`, `build_tool_catalog`, `build_planning_messages`, `parse_tool_call`, and `build_tool_result_messages` for `ChatService`.

- [ ] **Step 1: Write the failing tests**

Add tests that define the exact protocol:

```python
from app.models import ToolDefinition
from app.services.tool_calling import (
    ToolCallRequest,
    build_planning_messages,
    build_tool_catalog,
    build_tool_result_messages,
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


def test_catalog_contains_only_enabled_mcp_details():
    catalog = build_tool_catalog([mcp_tool()])
    assert "mcp:weather:weather" in catalog
    assert "查询城市天气" in catalog
    assert '"city"' in catalog


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
    assert parse_tool_call("not json") is None


def test_prompts_include_query_context_and_tool_result():
    planning = build_planning_messages([], "上海天气如何", "无检索资料", [mcp_tool()])
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
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider tests/test_tool_calling.py
```

Expected: collection fails because `app.services.tool_calling` and its public interfaces do not exist yet.

- [ ] **Step 3: Implement the minimal pure module**

Implement `ToolCallRequest` as a frozen dataclass. `build_tool_catalog()` must include only `kind == "mcp" and enabled`; serialize each tool as compact JSON containing `tool_id`, `name`, `description`, and `input_schema`. `build_planning_messages()` must produce a system message requiring exactly `{"tool_call": null}` or an object and a user message containing history, context, query and catalog. `parse_tool_call()` must inspect the complete string, strip one Markdown JSON fence if present, parse an object, require a `tool_call` object, require a non-empty string `tool_id`, and require `arguments` to be a dict (default `{}` if omitted). It must return `None` for all malformed or null cases. `build_tool_result_messages()` must serialize the tool result with `ensure_ascii=False` and include the original query and context.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the same command. Expected: all tests in `tests/test_tool_calling.py` pass.

- [ ] **Step 5: Refactor only after green**

Keep the module independent of Qt, `MCPClientService`, `LocalLLM`, filesystem and subprocesses. Re-run the focused tests after any cleanup.

---

### Task 2: Teach ChatService to plan and execute one MCP call

**Files:**
- Modify: `app/services/chat.py` (`ChatService.__init__` and `answer`)
- Modify: `tests/test_chat.py`

**Interfaces:**
- Consumes: `ToolRegistry.list_tools()`, `ToolRegistry.get()`, `ToolRegistry.call()`, and Task 1 protocol functions.
- Produces: existing `ChatEvent` stream with a generic MCP `tool` payload and final `done` payload.

- [ ] **Step 1: Add failing service tests**

Add a fake registry and a planning-capable fake LLM. The fake LLM returns the planning JSON on its first call and final text on the second call:

```python
from app.models import ToolDefinition
from app.services.mcp_client import MCPCallResult


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
            input_schema={"type": "object"},
        )
        self.result = result or MCPCallResult(True, ["28 度"], {"temperature": 28})

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


def test_chat_service_calls_enabled_mcp_tool_and_uses_result_in_final_prompt():
    registry = FakeToolRegistry()
    llm = PlanningLLM(
        '{"tool_call":{"tool_id":"mcp:weather:weather","arguments":{"city":"上海"}}}'
    )
    service = ChatService(FakeRetrieval([]), lambda model_id: llm, tool_registry=registry)

    events = list(service.answer("上海天气如何", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == [("mcp:weather:weather", {"city": "上海"})]
    assert [event.kind for event in events] == [
        "status", "citation", "status", "tool", "status", "token", "done"
    ]
    assert events[3].payload["tool_id"] == "mcp:weather:weather"
    assert events[3].payload["result"].structured_content == {"temperature": 28}
    assert "temperature" in llm.prompts[1][-1]["content"]


def test_chat_service_skips_mcp_when_model_returns_null_call():
    registry = FakeToolRegistry()
    llm = PlanningLLM('{"tool_call":null}')
    service = ChatService(FakeRetrieval([]), lambda model_id: llm, tool_registry=registry)

    events = list(service.answer("你好", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == []
    assert not any(event.kind == "tool" for event in events)
    assert len(llm.prompts) == 2


def test_chat_service_rejects_unknown_mcp_tool_without_calling_registry():
    registry = FakeToolRegistry()
    llm = PlanningLLM(
        '{"tool_call":{"tool_id":"mcp:unknown:run","arguments":{}}}'
    )
    service = ChatService(FakeRetrieval([]), lambda model_id: llm, tool_registry=registry)

    events = list(service.answer("运行未知工具", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == []
    assert not any(event.kind == "tool" for event in events)
    assert len(llm.prompts) == 2


def test_chat_service_preserves_calculator_shortcut_with_registry():
    registry = FakeToolRegistry()
    llm = FakeLLM()
    calculator = FakeCalculator()
    service = ChatService(FakeRetrieval([]), lambda model_id: llm, calculator, registry)

    list(service.answer("计算 123 + 456", "kb-ai", "qwen-1.5b", []))

    assert registry.calls == []
    assert len(llm.prompts) == 1
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider tests/test_chat.py
```

Expected: new tests fail because `ChatService` has no `tool_registry` parameter and no MCP planning path.

- [ ] **Step 3: Implement the minimal ChatService orchestration**

Add an optional `tool_registry=None` constructor parameter. After the existing calculator shortcut and knowledge-base citation/context construction:

1. Read `mcp_tools = [tool for tool in registry.list_tools() if tool.kind == "mcp" and tool.enabled]`.
2. If the list is non-empty, yield a planning status, call `llm.generate_stream(build_planning_messages(...))`, join the planning tokens, and parse the result.
3. If a request exists, look up the tool again with `registry.get(request.tool_id)`. Require `kind == "mcp"` and `enabled`; otherwise treat it as no-call and continue to final generation.
4. Call `registry.call(request.tool_id, request.arguments)`. Convert `MCPCallResult` or an exception into a JSON-safe result payload without raising from the generator.
5. Yield one generic `tool` event with `tool_id`, `name`, `source`, `arguments`, and the original result object or normalized error dict. Keep the result object available to the UI and persistence layer.
6. Build final messages with Task 1 and stream the final tokens. If no valid call occurs, still build a normal final prompt and make exactly one final generation after the planning response.
7. Put `citations` and a serializable list of tool calls in `done`. Do not run planning for calculator requests or when there are no enabled MCP tools.

Do not expose planning JSON as `token` events. Do not retry tools or recursively re-plan.

- [ ] **Step 4: Run focused tests and existing chat tests**

Run:

```powershell
G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider tests/test_chat.py
```

Expected: new MCP tests and all existing calculator/retrieval tests pass. If event ordering differs, update implementation to preserve the existing non-MCP order rather than weakening assertions.

- [ ] **Step 5: Refactor after green**

Extract only small private helpers for normalizing MCP results and converting tool events to serializable records. Keep the calculator branch unchanged and re-run `tests/test_chat.py`.

---

### Task 3: Inject the shared registry into the UI chat service

**Files:**
- Modify: `app/ui/main_window.py` (`_chat_service`)
- Modify: `tests/test_ui_smoke.py` only if a constructor/service wiring assertion is needed

**Interfaces:**
- Consumes: Task 2 `ChatService(..., tool_registry=...)`.
- Produces: chat workers use the same registry instance already refreshed by Tool Center.

- [ ] **Step 1: Write the failing wiring test**

Add a small test around `_chat_service()` using an existing MainWindow fixture or a lightweight object with `state`, `tool_registry`, `_retrieval`, and `_llm_factory` attributes:

```python
def test_main_window_chat_service_uses_shared_tool_registry(window):
    service = window._chat_service()
    assert service.tool_registry is window.tool_registry
```

If the existing UI fixture cannot safely construct a window in headless mode, test the extracted factory helper instead; do not launch a real model.

- [ ] **Step 2: Run the focused test and verify RED**

Run the selected test with `QT_QPA_PLATFORM=offscreen`. Expected: the service has no `tool_registry` attribute or the identity assertion fails.

- [ ] **Step 3: Implement one-line dependency injection**

Change `_chat_service()` from:

```python
return ChatService(self._retrieval(), self._llm_factory)
```

to:

```python
return ChatService(
    self._retrieval(),
    self._llm_factory,
    tool_registry=self.tool_registry,
)
```

Do not create a second `ToolRegistry`; MCP discovery and chat must share the same refreshed registry.

- [ ] **Step 4: Run the focused UI test and existing smoke tests**

Run the selected test and then:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider tests/test_ui_smoke.py
```

Expected: both pass without loading a real LLM or starting a real MCP server.

---

### Task 4: Render generic MCP tool events in chat history

**Files:**
- Modify: `app/ui/chat_page.py` (`append_tool_call`)
- Modify: `tests/test_ui_smoke.py` or the existing chat-page test location

**Interfaces:**
- Consumes: Task 2 tool payload fields `tool_id`, `name`, `source`, `arguments`, and an `MCPCallResult` or normalized result dict.
- Produces: a readable non-bubble tool record that supports both calculator and MCP calls and persists through `ChatMessage.tool_calls`.

- [ ] **Step 1: Write the failing UI behavior test**

Create a `ChatPage`, append a payload shaped like:

```python
{
    "tool_id": "mcp:weather:weather",
    "name": "天气查询",
    "source": "天气服务",
    "arguments": {"city": "上海"},
    "result": {"success": True, "content": ["28 度"], "structured_content": {"temperature": 28}},
}
```

Assert the list has one tool row and its displayed text contains the tool name, city and result; assert no exception occurs for a failed MCP result and for the existing calculator payload.

- [ ] **Step 2: Run the focused test and verify RED**

Run the focused UI test offscreen. Expected: current `append_tool_call()` assumes `result` is a dict with calculator fields and either omits MCP details or raises when given `MCPCallResult`.

- [ ] **Step 3: Implement generic display normalization**

Update `append_tool_call()` to:

1. Read a dataclass result through `success`, `content`, `structured_content`, and `error` attributes when present.
2. Read a dict result through existing keys.
3. Render a compact tool record containing `工具调用 · <name>`, optional source, JSON arguments, and either structured/content result or a readable error.
4. Preserve the existing non-bubble `ToolCallLabel` style and list-item sizing.
5. Avoid displaying MCP server command, cwd or environment values.

- [ ] **Step 4: Run focused UI tests and full chat tests**

Run the focused UI test and `tests/test_chat.py`. Expected: calculator display and MCP display both pass.

---

### Task 5: Add integration coverage with the repository MCP server

**Files:**
- Modify: `tests/test_mcp_client.py` only if a reusable fake/result helper is needed
- Modify: `tests/test_chat.py`
- Create: `tests/test_chat_mcp_integration.py` if the fake registry tests and real stdio smoke test are clearer in a separate file

**Interfaces:**
- Consumes: all production interfaces from Tasks 1–4 and `tests/mcp_test_server.py`.
- Produces: deterministic proof that ChatService can call a real local MCP stdio server through `MCPClientService`.

- [ ] **Step 1: Write the failing real-stdio smoke test**

Use `local_test_server()` from `tests/test_mcp_client.py`, create a `ToolRegistry` with `LocalStateStore(tmp_path)` and the real `MCPClientService`, save the server definition, refresh tools, and use a planning fake LLM that requests the discovered `repeat` tool with `{"text":"from chat"}`. Assert the final events contain one tool event, the registry call reaches the server, and the final prompt contains `from chat`.

- [ ] **Step 2: Run the smoke test and verify RED**

Run only the new test. Expected: it fails before the ChatService integration exists, while the lower-level MCP client tests remain green.

- [ ] **Step 3: Fix only integration gaps**

Use the already implemented real `ToolRegistry` and `MCPClientService`; do not add a second MCP transport or bypass the registry in the test.

- [ ] **Step 4: Run the smoke test and the MCP tests**

Run:

```powershell
G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider tests/test_mcp_client.py tests/test_tool_registry.py tests/test_chat_mcp_integration.py
```

Expected: all pass without network access.

---

### Task 6: Full verification and documentation update

**Files:**
- Modify: `README.md` with the actual chat-call flow and first-version limitations
- Modify: `docs/LOCALMIND_SESSION_HANDOFF.md` with the new ChatService MCP path and test commands

- [ ] **Step 1: Update user-facing documentation**

Document how to configure and enable a local MCP Server in Tool Center, explain that chat only uses enabled/discovered tools, show a minimal planning example, and state the one-call/no-remote limitation.

- [ ] **Step 2: Run the complete test suite**

Run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider
```

Expected: exit code 0 and zero failures.

- [ ] **Step 3: Run a direct local MCP smoke test**

Run the real-stdio integration test again and inspect that the output contains a successful tool event and final model prompt. No network request is allowed.

- [ ] **Step 4: Review the diff for scope and secrets**

Run:

```powershell
git status --short
git diff --check
git diff -- README.md docs/LOCALMIND_SESSION_HANDOFF.md app/services/tool_calling.py app/services/chat.py app/ui/main_window.py app/ui/chat_page.py tests/test_tool_calling.py tests/test_chat.py tests/test_chat_mcp_integration.py
```

Confirm no MCP command, working directory, environment variable, local model path, or user document content was accidentally added to documentation or tests.

- [ ] **Step 5: Commit only if repository permissions allow it**

Stage only the feature files and commit:

```powershell
git add app/services/tool_calling.py app/services/chat.py app/ui/main_window.py app/ui/chat_page.py tests/test_tool_calling.py tests/test_chat.py tests/test_chat_mcp_integration.py README.md docs/LOCALMIND_SESSION_HANDOFF.md
git commit -m "feat: let local LLM call enabled MCP tools"
```

If `.git/index.lock` remains unwritable, report the exact permission error and leave all working-tree changes intact; do not delete the lock file automatically.
