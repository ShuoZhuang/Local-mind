# 工具中心本地/远程筛选与 MCP 刷新实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工具中心增加本地工具与远程工具筛选，并在停用最后一个 MCP Server 后即时清除过期远程工具卡片。

**Architecture:** `ToolCenterPage` 依据 `ToolDefinition.kind` 过滤两组已注册工具与本地能力；它不改变注册表的数据来源。`MainWindow._discover_mcp_tools()` 始终通过现有后台 `MCPWorker` 调用 `ToolRegistry.refresh_mcp_tools()`，让注册表清除禁用 Server 的缓存后再刷新卡片。

**Tech Stack:** Python 3.10、PySide6、pytest。

## Global Constraints

- `kind == "mcp"` 为远程工具，`kind == "capability"` 为本地能力，其余可调用工具为本地工具。
- “已启用”显示所有 `enabled=True` 的可调用工具，不显示本地能力。
- 不修改 MCP transport；stdio MCP 工具使用“远程工具”仅作为产品分类名称。
- 不修改 `data/` 内用户知识库数据，也不删除工具或能力的 `category` 元数据。
- 直接在 `main` 工作区修改；不覆盖当前工作区既有未提交 MCP/UI 改动。
- 测试命令使用 `G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider`。

---

### Task 1: 增加工具来源筛选

**Files:**
- Modify: `app/ui/tool_center_page.py:325-465`
- Modify: `tests/test_tool_center.py:101-127`

**Interfaces:**
- Consumes: `ToolDefinition.kind: str`、`ToolDefinition.enabled: bool`、`ToolCenterPage.visible_tool_ids()`、`ToolCenterPage.visible_capability_ids()`。
- Produces: `category_buttons` 顺序为 `["全部", "已启用", "本地工具", "远程工具", "本地能力"]`；本地工具与远程工具筛选只作用于可调用工具，能力筛选只作用于能力卡片。

- [ ] **Step 1: 写入失败测试**

在 `tests/test_tool_center.py` 创建一个带三类定义的测试：本地 `ToolDefinition(id="calculator", kind="tool", enabled=True)`、远程 `ToolDefinition(id="mcp:demo:repeat", kind="mcp", enabled=True)`、以及 `DEFAULT_LOCAL_CAPABILITIES`。断言按钮顺序如下：

```python
assert list(page.category_buttons) == [
    "全部", "已启用", "本地工具", "远程工具", "本地能力",
]
```

并分别断言点击“本地工具”只显示 `calculator`，“远程工具”只显示 `mcp:demo:repeat`，点击“本地能力”时两个 `visible_tool_ids()` 结果为空但所有能力 ID 可见，“已启用”显示上述两个工具且不显示能力。保留已有搜索和重排测试，但不再使用被删除的旧分类筛选。

- [ ] **Step 2: 运行目标测试并确认失败**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest tests/test_tool_center.py -q -p no:anyio -p no:cacheprovider
```

预期：新增测试因按钮列表缺少“本地工具”“远程工具”而失败。

- [ ] **Step 3: 写入最小实现**

在筛选按钮创建处使用：

```python
for category in ("全部", "已启用", "本地工具", "远程工具", "本地能力"):
```

在可调用工具的 `_refresh_visibility()` 循环中使用：

```python
matches_category = (
    category == "全部"
    or (category == "已启用" and tool.enabled)
    or (category == "本地工具" and tool.kind != "mcp")
    or (category == "远程工具" and tool.kind == "mcp")
)
```

本地能力循环保持仅在 `category in {"全部", "本地能力"}` 时匹配。不要依据 `id.startswith("mcp:")` 或 `category == "MCP"` 分类。

- [ ] **Step 4: 运行目标测试并确认通过**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest tests/test_tool_center.py -q -p no:anyio -p no:cacheprovider
```

预期：`tests/test_tool_center.py` 全部通过。

- [ ] **Step 5: 提交本任务文件**

仅在索引可不含既有无关改动时运行：

```powershell
git add -- app/ui/tool_center_page.py tests/test_tool_center.py
git commit -m "feat: add local and remote tool filters"
```

如两个文件包含既有无关未提交改动，则不要创建混合提交；在任务报告中写明该阻塞。

### Task 2: 停用 MCP Server 后刷新注册表与卡片

**Files:**
- Modify: `app/ui/main_window.py:201-211`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `LocalStateStore.list_mcp_servers() -> list[MCPServerDefinition]`、`ToolRegistry.refresh_mcp_tools() -> list[ToolDefinition]`、`MainWindow._start_mcp_worker(operation, on_finished)`。
- Produces: 每次 `servers_changed` 触发的 `_discover_mcp_tools()` 都刷新 MCP 注册表；`_on_mcp_discovery_finished()` 随后重建工具中心卡片。

- [ ] **Step 1: 写入失败回归测试**

在 `tests/test_ui_smoke.py` 新增 `test_disabling_last_mcp_server_refreshes_tool_center`。创建 `MainWindow`，用一个启用的临时 `MCPServerDefinition` 保存到 state，并替换 `window.tool_registry` 为具备 `refresh_mcp_tools()`、`list_tools()` 与 `server_errors()` 的 fake。令 fake 初始返回一个 `ToolDefinition(id="mcp:demo:repeat", kind="mcp", enabled=True)`，再将 Server 保存为 `enabled=False`。把 `window._start_mcp_worker` 替换为同步执行 `operation()` 后调用 `on_finished(result)` 的函数，随后调用 `window._discover_mcp_tools()`。

断言 fake 的 `refresh_mcp_tools()` 被调用一次，fake `list_tools()` 不再返回 MCP 工具，并且 `window.tool_center_page.tool("mcp:demo:repeat") is None`。当前实现因早退分支导致第一个断言失败。

- [ ] **Step 2: 运行回归测试并确认失败**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest tests/test_ui_smoke.py::test_disabling_last_mcp_server_refreshes_tool_center -q -p no:anyio -p no:cacheprovider
```

预期：测试失败，原因是 `_discover_mcp_tools()` 在没有启用 Server 时没有调用 `_start_mcp_worker()`。

- [ ] **Step 3: 写入根因修复**

删除 `_discover_mcp_tools()` 中的无启用 Server 早退分支，使每次调用都复用既有后台刷新路径：

```python
self._start_mcp_worker(
    lambda: self.tool_registry.refresh_mcp_tools(),
    self._on_mcp_discovery_finished,
)
```

仅在至少一个 Server 启用时显示“正在发现已启用 MCP Server 中的工具…”状态文本；无启用 Server 时不显示成功发现提示，但仍通过 `_on_mcp_discovery_finished()` 刷新卡片。

- [ ] **Step 4: 运行回归测试并确认通过**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest tests/test_ui_smoke.py::test_disabling_last_mcp_server_refreshes_tool_center -q -p no:anyio -p no:cacheprovider
```

预期：测试通过，且 MCP 工具已从注册表与工具中心移除。

- [ ] **Step 5: 运行相关 UI/MCP 测试**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest tests/test_ui_smoke.py tests/test_mcp_server_dialog.py tests/test_tool_registry.py -q -p no:anyio -p no:cacheprovider
```

预期：全部通过。

- [ ] **Step 6: 提交本任务文件**

仅在索引可不含既有无关改动时运行：

```powershell
git add -- app/ui/main_window.py tests/test_ui_smoke.py
git commit -m "fix: refresh tools after MCP server changes"
```

如文件包含既有无关未提交改动，则不要创建混合提交；在任务报告中写明该阻塞。
