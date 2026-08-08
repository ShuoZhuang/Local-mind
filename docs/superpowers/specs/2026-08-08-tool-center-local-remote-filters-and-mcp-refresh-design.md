# 工具中心本地/远程筛选与 MCP 刷新设计

## 目标

工具中心在现有“全部”“已启用”“本地能力”之外新增“本地工具”和“远程工具”筛选，并在 MCP Server 配置停用后立即移除对应工具卡片。

## 分类规则

- `ToolDefinition.kind == "mcp"`：远程工具。
- `ToolDefinition.kind == "capability"`：本地能力。
- 其余可调用工具：本地工具。
- “已启用”显示所有 `enabled=True` 的可调用工具，包括本地工具与远程工具，但不显示本地能力。
- “全部”显示所有可调用工具和全部本地能力。

分类只使用 `kind`，不使用工具名称、`category` 文本或 MCP ID 前缀；`category` 保留用于卡片信息与搜索。

## MCP 配置变更刷新

`MCPServerDialog.servers_changed` 继续触发主窗口的 MCP 刷新入口。有启用 Server 时，该入口在后台调用 `ToolRegistry.refresh_mcp_tools()`；没有启用 Server 时，直接同步清空注册表并刷新卡片，因为此时没有外部发现 I/O。两条路径都会在完成后调用 `_refresh_registered_tools()`。

`refresh_mcp_tools()` 先清空内存中的 MCP 工具与 Server 缓存，再仅发现启用 Server 的工具。故当最后一个 Server 被停用时，刷新完成后注册表不再暴露旧 MCP 工具，工具中心随之移除远程工具卡片。无启用 Server 时采用同步清理路径，避免为无 I/O 操作创建短生命周期 Qt 线程。

## 测试

- 工具中心测试覆盖五个筛选按钮的准确顺序，以及本地工具、远程工具、本地能力和已启用视图的可见集合。
- 注册表测试继续确保本地工具为 `kind="tool"`、MCP 工具为 `kind="mcp"`。
- 主窗口回归测试复现“停用最后一个 MCP Server”：配置变更触发刷新后，注册表和工具中心均不再包含该 MCP 工具，并验证无启用 Server 时不会创建后台发现线程。

## 范围与约束

- 不改变 MCP transport；当前 stdio MCP 工具按产品分类称为“远程工具”，不表示 HTTP/SSE 网络传输。
- 不修改 `data/` 中的用户知识库数据。
- 不删除工具或能力的 `category` 元数据。
- 保留当前工作区的既有未提交 MCP/UI 改动；仅触及本功能必要的文件。
