# LocalMind LLM 自动调用本地 MCP 工具设计

## 目标

让 LocalMind 的本地 LLM 能根据用户问题自主决定是否调用已经在工具中心启用并发现的本地 MCP Tool；工具执行完成后，模型继续生成最终回答，并在聊天记录中保留可读的工具调用记录。

## 范围与约束

- 只调用本机配置的 `stdio` MCP Server，不加入远程 HTTP/SSE MCP。
- 只允许调用 `ToolRegistry` 中已经发现且启用的 MCP Tool。
- 每次用户请求最多执行一次 MCP Tool，避免小模型进入循环调用。
- 保留现有计算器的优先路由和知识库检索逻辑。
- 不让模型直接执行命令；模型只能提出工具 ID 和 JSON 参数，实际执行必须经过注册表校验。
- 工具调用失败时，错误结果回传给模型，由模型生成可读的失败说明。
- 工具调用记录需要继续写入 `ChatMessage.tool_calls`，并沿用聊天页现有的工具事件展示机制。

## 当前问题

本地 MCP Client、ToolRegistry 和工具中心已经实现了工具发现与手动测试，但 `ChatService.answer()` 目前只自动路由计算器。LLM 没有看到 MCP 工具目录，也没有机会提出调用请求，因此 MCP Tool 不能从聊天中被调用。

## 方案

采用“模型规划 + 应用校验执行 + 模型总结”的混合协议：

```text
用户问题
  ↓
计算器确定性路由（已有逻辑）
  ↓（非计算器）
知识库检索
  ↓
生成包含工具目录的规划提示词
  ↓
本地 LLM 输出纯文本或严格 JSON 工具请求
  ↓
应用解析并校验 tool_id、参数对象和启用状态
  ↓（有效请求）
ToolRegistry.call() → MCPClientService.call_tool()
  ↓
发送 tool 结果给 LLM
  ↓
流式生成最终回答
```

### 规划协议

应用会为模型提供当前可用 MCP Tool 的最小信息：工具 ID、显示名称、说明和输入 Schema。模型必须在以下二选一格式中输出：

```json
{"tool_call":{"tool_id":"mcp:server-id:weather","arguments":{"city":"上海"}}}
```

或：

```json
{"tool_call":null}
```

为了适配当前本地 Qwen 流式接口，应用会收集规划阶段输出后再解析 JSON；不要求模型具备原生 Function Calling API。解析器只接受完整 JSON 对象，允许从 Markdown 代码围栏中提取 JSON，但不会执行 JSON 之外的代码或命令。

### 校验规则

1. `tool_call` 必须是对象或 `null`。
2. `tool_id` 必须存在于当前 `ToolRegistry`，且工具 `kind == "mcp"`、`enabled == True`。
3. `arguments` 必须是 JSON 对象；缺失时使用空对象。
4. 调用前重新从当前注册表取得工具，避免聊天期间 Server 被禁用后仍可调用。
5. 规划输出无法解析、工具不存在、参数不是对象或 MCP 返回错误时，不抛出到 UI；改为生成可读错误事件，并允许模型根据错误结果回答。

### 最终回答协议

工具成功或失败后，第二次模型提示词包含：用户问题、知识库上下文、工具名称、工具参数和工具结果。系统提示明确要求：

- 工具结果是唯一可信的工具事实；
- 不要声称工具没有调用；
- 结果不足时明确说明不足；
- 最终回答继续使用 Markdown。

如果模型没有请求工具，则只进行一次普通最终回答，不增加工具记录。

## 组件设计

### `app/services/tool_calling.py`

新增一个纯逻辑模块，负责规划输出协议，不负责启动 MCP：

- `ToolCallRequest(tool_id: str, arguments: dict[str, Any])`
- `build_tool_catalog(tools: Sequence[ToolDefinition]) -> str`
- `build_planning_messages(history, query, context, tools) -> list[dict[str, str]]`
- `parse_tool_call(text: str) -> ToolCallRequest | None`
- `build_tool_result_messages(history, query, context, request, result) -> list[dict[str, str]]`

解析和提示词可以脱离 Qt、模型和 MCP 进程单元测试。

### `app/services/chat.py`

扩展 `ChatService`：

- 构造函数接受可选 `tool_registry`。
- 非计算器请求在知识库检索后，若注册表存在已启用 MCP Tool，则执行一次规划阶段。
- 规划阶段只消费模型文本，不向 UI 发 token，避免把 JSON 暴露给用户。
- 有效工具请求先发出 `status`，调用注册表，再发出 `tool` 事件；工具事件统一包含 `tool_id`、`name`、`arguments`、`result`、`source`。
- 工具阶段结束后再流式生成最终 token，并在 `done` 中携带 citations 与 tool_calls。
- 无 MCP Tool 时保持现有调用次数、事件顺序和普通回答行为不变。

### `app/ui/main_window.py`

- `_chat_service()` 将共享的 `self.tool_registry` 注入 `ChatService`。
- 继续沿用已有 `StreamWorker`，因为 MCP 调用发生在聊天 worker 线程中，不阻塞 Qt 主线程。
- 将 MCP 工具事件转换成现有聊天记录格式；工具调用记录中不显示敏感环境变量和 Server 启动命令，只显示工具名、参数和返回内容摘要。

### `app/ui/chat_page.py`

第一版不新增复杂 UI 开关，聊天默认允许调用“工具中心中已经启用”的 MCP Tool。工具调用继续通过现有 `append_tool_call()` 显示；如果现有展示只理解计算器字段，则扩展为同时支持 MCP 的通用字段。

## 错误处理

- 没有 MCP Tool：跳过规划阶段，保持普通回答。
- 规划 JSON 无法解析：视为“不调用工具”，直接进入普通回答，不把解析错误暴露给用户。
- Tool ID 不存在或已禁用：生成内部错误结果，不执行调用。
- MCP Server 启动失败、协议失败或工具返回 `is_error`：记录失败工具事件，把错误文本交回模型。
- 用户停止生成：停止当前流式 worker；不会启动新的 MCP 调用循环。

## 测试设计

新增纯逻辑测试：

- 工具目录包含真实 MCP Tool 的 ID、说明和 Schema。
- 解析裸 JSON、Markdown 代码围栏 JSON、`tool_call: null`。
- 拒绝非对象参数、未知字段结构和未知工具 ID。
- 工具结果提示词包含结构化结果和原始问题。

新增聊天服务测试：

- 模型请求有效 MCP Tool 时，事件顺序为规划状态、工具事件、最终 token、完成事件。
- 注册表收到正确的工具 ID 和参数。
- 第二次模型提示词包含 MCP 返回结果。
- 模型输出不调用工具时只生成一次最终回答。
- MCP 调用失败时仍能生成最终回答，且工具失败记录可持久化。
- 没有 MCP 工具时现有知识库检索测试保持通过。

验收时运行完整测试集，并使用仓库中的 `tests/mcp_test_server.py` 做一次本地真实 stdio MCP 调用冒烟测试。

## 不在本次范围内

- 多轮工具调用或工具调用循环。
- 并行调用多个 MCP Tool。
- 远程 MCP Server、OAuth 和密钥管理。
- 自动安装 MCP Server。
- 把 LocalMind 暴露成 MCP Server。
- 让知识库检索、Embedding、文档解析伪装成可供 LLM 选择的 MCP Tool。
