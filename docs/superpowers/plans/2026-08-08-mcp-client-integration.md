# MCP Client 接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 LocalMind 通过本机 stdio 连接用户配置的 MCP Server，发现工具、在工具中心展示，并能用 JSON 参数进行手动测试调用。

**Architecture:** `LocalStateStore` 持久化 MCP Server 配置；`MCPClientService` 通过官方 SDK 为一次发现或调用建立、初始化并关闭会话；`ToolRegistry` 将现有高级计算器和已发现的 MCP Tool 汇总为统一工具记录。工具中心和右侧详情只读取注册表，主窗口负责配置对话框、后台发现/测试和刷新 UI。

**Tech Stack:** Python 3.10、PySide6、官方 `mcp` Python SDK（stdio transport）、pytest。

## Global Constraints

- 第一版只支持用户显式配置的本机 stdio MCP Server。
- 不实现 Streamable HTTP、SSE、LocalMind MCP Server 或聊天自动工具选择。
- 不预置第三方 Server、网址、令牌或网络请求。
- 启动命令只能来自用户在配置界面确认后保存的配置。
- 现有 `calculator_tool` 与 `CalculatorRouter` 的聊天行为不得改变。
- 所有 MCP 测试必须使用本地临时 Server，不能依赖网络。

---

## 文件结构

- 修改：`requirements.txt` — 增加官方 MCP SDK 依赖。
- 修改：`app/models.py` — 定义持久化的 MCP Server 与运行时工具记录。
- 修改：`app/services/storage.py` — 保存、读取、更新、删除 `mcp_servers.json`。
- 创建：`app/services/mcp_client.py` — stdio 会话、工具发现、工具调用和结果转换。
- 创建：`app/services/tool_registry.py` — 汇总本地计算器与已发现 MCP Tool。
- 修改：`app/ui/tool_center_page.py` — 用统一工具记录渲染 MCP 标签、来源、Schema 和 JSON 测试输入。
- 创建：`app/ui/mcp_server_dialog.py` — 添加、编辑、启用、停用、删除和重新发现 Server 的配置界面。
- 修改：`app/ui/main_window.py` — 创建注册表、驱动发现/调用、把 MCP Server 管理入口接到工具中心。
- 修改：`app/ui/workers.py` — 添加不会阻塞 PySide 主线程的 MCP 发现与调用 worker。
- 创建：`tests/mcp_test_server.py` — 本地测试专用的最小 stdio MCP Server。
- 创建：`tests/test_mcp_client.py` — Client 发现、调用和错误结果回归测试。
- 创建：`tests/test_tool_registry.py` — 统一注册表测试。
- 修改：`tests/test_storage.py` — MCP Server 配置持久化测试。
- 修改：`tests/test_tool_center.py` — MCP Tool 卡片、Schema 与 JSON 测试输入 UI 测试。
- 修改：`README.md`、`config.example.json` — 说明 MCP 仅支持本机 stdio 配置，不含凭据。

## Task 1: MCP 配置模型与持久化

**Files:**
- Modify: `app/models.py`
- Modify: `app/services/storage.py`
- Modify: `tests/test_storage.py`

**Interfaces:**
- Produces `MCPServerDefinition.new(name, command, args=(), cwd=None, env=None, enabled=True)`。
- Produces `MCPServerDefinition.to_dict()` 与 `MCPServerDefinition.from_dict(data)`。
- Produces `LocalStateStore.list_mcp_servers()`, `save_mcp_server(server)`, `delete_mcp_server(server_id)`。

- [ ] **Step 1: Write the failing tests**

```python
def test_mcp_server_definitions_round_trip_through_state(tmp_path):
    store = LocalStateStore(tmp_path)
    server = MCPServerDefinition.new(
        "本地测试服务", "python", ("-m", "tests.mcp_test_server"), cwd="C:/tools"
    )

    store.save_mcp_server(server)

    assert store.list_mcp_servers() == [server]


def test_deleting_mcp_server_removes_only_requested_configuration(tmp_path):
    store = LocalStateStore(tmp_path)
    kept = MCPServerDefinition.new("保留", "python")
    removed = MCPServerDefinition.new("删除", "node")
    store.save_mcp_server(kept)
    store.save_mcp_server(removed)

    store.delete_mcp_server(removed.id)

    assert [item.id for item in store.list_mcp_servers()] == [kept.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py -k mcp -v`

Expected: FAIL because `MCPServerDefinition` and MCP storage methods do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class MCPServerDefinition:
    id: str
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def new(cls, name, command, args=(), cwd=None, env=None, enabled=True):
        timestamp = now_iso()
        return cls(f"mcp-{uuid4().hex[:12]}", name.strip(), command.strip(),
                   list(args), cwd or None, dict(env or {}), bool(enabled), timestamp, timestamp)
```

Add `self.mcp_servers_path = self.root / "mcp_servers.json"` and persist records using the existing `_read_json` and `_write_json` helpers. `save_mcp_server` must replace a matching ID, update `updated_at`, and preserve all other configurations.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py -k mcp -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models.py app/services/storage.py tests/test_storage.py
git commit -m "feat: persist MCP server configurations"
```

## Task 2: stdio MCP Client 服务

**Files:**
- Modify: `requirements.txt`
- Create: `app/services/mcp_client.py`
- Create: `tests/mcp_test_server.py`
- Create: `tests/test_mcp_client.py`

**Interfaces:**
- Consumes `MCPServerDefinition` from Task 1.
- Produces `MCPToolInfo(name, title, description, input_schema)`。
- Produces `MCPCallResult(success, content, structured_content, is_error, error)`。
- Produces synchronous methods `MCPClientService.discover(server)` and `MCPClientService.call_tool(server, tool_name, arguments)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_client_discovers_tools_from_local_stdio_server(mcp_server):
    tools = MCPClientService().discover(mcp_server)

    assert [(tool.name, tool.description) for tool in tools] == [
        ("repeat", "返回传入的文字")
    ]
    assert tools[0].input_schema["required"] == ["text"]


def test_client_calls_tool_and_keeps_structured_result(mcp_server):
    result = MCPClientService().call_tool(mcp_server, "repeat", {"text": "LocalMind"})

    assert result.success is True
    assert result.structured_content == {"text": "LocalMind"}
    assert result.content == ["LocalMind"]


def test_client_returns_readable_error_when_command_is_missing():
    server = MCPServerDefinition.new("不存在", "missing-mcp-command")

    result = MCPClientService().call_tool(server, "repeat", {"text": "x"})

    assert result.success is False
    assert "missing-mcp-command" in result.error
```

`tests/mcp_test_server.py` must expose a real `repeat(text: str)` MCP Tool with text content and `{"text": text}` structured content. The `mcp_server` fixture must launch it with `sys.executable`, `-m`, and the test module name.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp_client.py -v`

Expected: FAIL because `MCPClientService` does not exist and the `mcp` dependency is not installed.

- [ ] **Step 3: Write minimal implementation**

Add `mcp>=1.0,<3` to `requirements.txt`. Implement the async private operation using the official SDK:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def _with_session(server, operation):
    params = StdioServerParameters(
        command=server.command,
        args=server.args,
        cwd=server.cwd,
        env={**os.environ, **server.env},
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await operation(session)
```

`discover` runs `session.list_tools()` and maps every Tool to `MCPToolInfo`. `call_tool` runs `session.call_tool(tool_name, arguments)`, preserves text content and structured content, and turns process, protocol and tool exceptions into `MCPCallResult(success=False, error=<readable text>)`. Public synchronous methods use `asyncio.run` and always close the session before returning.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mcp_client.py -v`

Expected: PASS with no network requests.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app/services/mcp_client.py tests/mcp_test_server.py tests/test_mcp_client.py
git commit -m "feat: add stdio MCP client service"
```

## Task 3: 统一 Tool Registry

**Files:**
- Modify: `app/models.py`
- Create: `app/services/tool_registry.py`
- Modify: `app/ui/tool_center_page.py`
- Create: `tests/test_tool_registry.py`
- Modify: `tests/test_tool_center.py`

**Interfaces:**
- Produces `ToolDefinition` in `app.models` with `source`, `input_schema`, `kind` and `enabled` fields.
- Produces `ToolRegistry.list_tools()`, `ToolRegistry.refresh_mcp_tools()`, `ToolRegistry.get(tool_id)` and `ToolRegistry.call(tool_id, arguments)`.
- MCP Tool ID format is `mcp:{server_id}:{tool_name}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_registry_combines_calculator_and_discovered_mcp_tools(fake_mcp_client):
    registry = ToolRegistry(store, fake_mcp_client)
    registry.refresh_mcp_tools()

    tools = registry.list_tools()

    assert [tool.id for tool in tools] == ["calculator", "mcp:mcp-demo:repeat"]
    assert tools[1].kind == "mcp"
    assert tools[1].source == "演示服务"
    assert tools[1].input_schema["required"] == ["text"]


def test_registry_does_not_list_disabled_servers(fake_mcp_client):
    store.save_mcp_server(MCPServerDefinition("mcp-off", "关闭", "python", enabled=False))

    assert ToolRegistry(store, fake_mcp_client).list_tools() == [calculator_definition()]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tool_registry.py -v`

Expected: FAIL because `ToolRegistry` and shared `ToolDefinition` do not exist.

- [ ] **Step 3: Write minimal implementation**

Move the `ToolDefinition` dataclass from `app/ui/tool_center_page.py` to `app/models.py` and re-export it from `tool_center_page.py` so existing imports remain valid. Add only these fields with safe defaults:

```python
source: str | None = None
input_schema: dict[str, Any] = field(default_factory=dict)
last_error: str | None = None
```

`ToolRegistry` must always create the existing calculator definition from `calculator_tool.schema()`. For every enabled MCP Server, `refresh_mcp_tools()` discovers tools and converts them into enabled `ToolDefinition` instances. Failed discovery produces no fake Tool card; it records the readable error by Server ID for the UI manager. `call` delegates calculator calls to `calculator_tool.run` and MCP calls to `MCPClientService.call_tool`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tool_registry.py tests/test_tool_center.py -v`

Expected: PASS; existing calculator and local capability assertions remain valid.

- [ ] **Step 5: Commit**

```bash
git add app/models.py app/services/tool_registry.py app/ui/tool_center_page.py tests/test_tool_registry.py tests/test_tool_center.py
git commit -m "feat: register MCP tools with local tools"
```

## Task 4: MCP Server 管理与工具中心详情

**Files:**
- Create: `app/ui/mcp_server_dialog.py`
- Modify: `app/ui/tool_center_page.py`
- Modify: `app/ui/main_window.py`
- Modify: `app/ui/workers.py`
- Modify: `tests/test_tool_center.py`
- Create: `tests/test_mcp_server_dialog.py`

**Interfaces:**
- `MCPServerDialog` emits `servers_changed` after a confirmed add, edit, enabled-state change or deletion.
- `ToolCenterPage.mcp_servers_requested` opens the dialog.
- `ToolDetailsPanel.test_requested` emits `(tool_id, arguments)` where `arguments` is a parsed JSON object.
- `MCPWorker` emits success or a readable error without blocking the Qt main thread.

- [ ] **Step 1: Write the failing tests**

```python
def test_mcp_server_dialog_validates_command_and_saves_server(tmp_path, qtbot):
    store = LocalStateStore(tmp_path)
    dialog = MCPServerDialog(store)
    dialog.name_input.setText("演示服务")
    dialog.command_input.setText("python")
    dialog.arguments_input.setPlainText('["-m", "tests.mcp_test_server"]')

    dialog.save_current_server()

    assert store.list_mcp_servers()[0].name == "演示服务"


def test_mcp_tool_details_parse_json_arguments_before_emitting(qtbot):
    panel = ToolDetailsPanel()
    panel.set_tool(mcp_repeat_definition())
    panel.arguments_input.setPlainText('{"text": "hi"}')
    spy = QSignalSpy(panel.test_requested)

    panel.test_button.click()

    assert spy.at(0) == ["mcp:mcp-demo:repeat", {"text": "hi"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_server_dialog.py tests/test_tool_center.py -k "mcp" -v`

Expected: FAIL because the dialog, JSON input and MCP signals do not exist.

- [ ] **Step 3: Write minimal implementation**

Create a modal `MCPServerDialog` containing a Server list plus fields for name, command, JSON args, optional working directory, optional JSON environment and enabled checkbox. Validate: name and command must be non-empty; args must be a JSON string array; env must be a JSON object whose values are converted to strings. Before saving show a confirmation message: “此命令会在本机执行，请只添加可信 MCP Server。”

Add a visible `管理 MCP Server` control in `ToolCenterPage`. For MCP Tools, `ToolDetailsPanel` displays source and pretty-printed input Schema, shows a `QPlainTextEdit` initialized to `{}`, and validates a JSON object before emitting a test signal. For calculator, keep the current one-click `2 + 2` test behavior. For local capabilities, keep test controls hidden.

In `MainWindow`, construct `ToolRegistry(self.state, MCPClientService())`, replace static `DEFAULT_TOOL_DEFINITIONS` loading with `registry.list_tools()`, connect management and test signals, and refresh cards/details after configuration changes. Use a `MCPWorker` for discovery and test calls; it receives a callable, emits `finished(object)` or `failed(str)`, and is hosted with the existing QThread lifetime list.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mcp_server_dialog.py tests/test_tool_center.py tests/test_ui_smoke.py -v`

Expected: PASS; tests run with `QT_QPA_PLATFORM=offscreen`.

- [ ] **Step 5: Commit**

```bash
git add app/ui/mcp_server_dialog.py app/ui/tool_center_page.py app/ui/main_window.py app/ui/workers.py tests/test_mcp_server_dialog.py tests/test_tool_center.py
git commit -m "feat: manage and test MCP tools in tool center"
```

## Task 5: 文档、安装与全量验证

**Files:**
- Modify: `README.md`
- Modify: `config.example.json`
- Modify: `docs/superpowers/specs/2026-08-08-mcp-client-integration-design.md`

**Interfaces:**
- Documents the exact local stdio scope and safety boundary.
- Documents that chat auto-routing and HTTP transports are not included.

- [ ] **Step 1: Write the failing documentation check**

```powershell
Select-String -LiteralPath README.md -Pattern "MCP Server", "stdio", "可信"
```

Expected: no MCP-specific documentation before edits.

- [ ] **Step 2: Run documentation check to verify it fails**

Run: `Select-String -LiteralPath README.md -Pattern "MCP Server", "stdio", "可信"`

Expected: no matching MCP usage section.

- [ ] **Step 3: Write minimal documentation**

Add a “MCP 本地接入” README section with an example configuration:

```text
名称：本地演示 MCP 服务
命令：python
参数：["-m", "my_mcp_server"]
```

State that LocalMind executes only user-approved local commands, only stdio is supported in this release, and tools are manually tested in the Tool Center. Add `"mcp_servers_file": "data/state/mcp_servers.json"` to `config.example.json` as documentation only; runtime still uses `AppConfig.state_dir`.

- [ ] **Step 4: Run documentation check and full verification**

Run: `pytest -q`

Expected: all tests pass; MCP tests use no network. Also run `python -m compileall app tools tests`.

- [ ] **Step 5: Commit**

```bash
git add README.md config.example.json docs/superpowers/specs/2026-08-08-mcp-client-integration-design.md
git commit -m "docs: explain local MCP integration"
```
