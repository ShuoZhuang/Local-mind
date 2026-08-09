# LocalMind MCP Client 接入设计

## 目标

让 LocalMind 作为 MCP Client 连接用户配置的本机 `stdio` MCP Server，发现其工具，并在工具中心展示和手动测试调用。第一版保持本地优先，不改变现有知识库检索与高级计算器的调用逻辑。

## 范围

本次实现包含：

- 使用官方 Python `mcp` SDK；
- 配置本机 `stdio` MCP Server 的名称、命令、参数、工作目录和启用状态；
- 在启动命令受用户显式配置的前提下，建立 MCP 会话、初始化、发现 `tools/list`；
- 把发现的工具转换为 LocalMind 统一工具记录；
- 在工具中心显示 Server 来源、连接状态、参数 Schema 和工具描述；
- 从工具详情页手动执行测试调用；
- 持久化配置到 `data/state/mcp_servers.json`；
- 用本地临时 MCP 测试 Server 覆盖发现、调用和错误处理。

本次不包含：

- Streamable HTTP、SSE 或远程 MCP Server；
- LocalMind 作为 MCP Server 向其他客户端暴露能力；
- 由 LLM 自动判断并调用 MCP Tool；
- 把第三方 MCP Server 或网络凭据预置进应用。

## 结构

```text
ToolCenterPage
      │
      ├── MCP Server 配置界面
      │         │
      │         ▼
      └── MCPClientService ── stdio ── 用户配置的 MCP Server
                    │                  │
                    │                  ├── initialize
                    │                  ├── tools/list
                    │                  └── tools/call
                    ▼
              ToolRegistry
               ├── 本地 calculator
               └── 已发现 MCP tools
```

### MCPServerDefinition

每台服务器使用下列字段：

- `id`：稳定 ID；
- `name`：显示名称；
- `command`：用户允许应用启动的可执行命令；
- `args`：命令参数数组；
- `cwd`：可选工作目录；
- `env`：可选环境变量映射；
- `enabled`：是否出现在工具发现与调用中；
- `created_at`、`updated_at`：记录配置变更。

不保存密码或令牌。需要凭据的 Server 应通过用户自行配置的本机环境、命令包装器或未来独立的凭据管理功能提供。

### MCPClientService

服务以“单次连接、单次操作、确保关闭”的方式工作：

1. 根据一个 `MCPServerDefinition` 启动标准输入输出子进程；
2. 建立并初始化 `ClientSession`；
3. 执行 `tools/list` 或 `tools/call`；
4. 将工具描述、文本内容、结构化内容和错误转换为普通 Python 数据；
5. 在退出前关闭会话和子进程。

这样能避免 PySide 主线程与长期异步事件循环之间的生命周期问题。将来聊天自动调用时可以复用相同的 `call_tool` 接口；如果性能需要，再引入持久会话池。

### ToolRegistry

注册表是工具中心的单一事实来源：

- 本地工具沿用 `calculator_tool.schema()`；
- MCP 工具使用 `mcp:{server_id}:{tool_name}` 作为 LocalMind 工具 ID；
- 工具记录包含类型（`local` 或 `mcp`）、来源 Server、描述、输入 Schema、启用状态和最近错误；
- 文档解析、分段、向量化等保留为“系统能力”，不冒充模型可调用 Tool。

## 用户界面

工具中心新增一个 MCP Server 管理入口：

- “添加 MCP Server”打开紧凑配置对话框；
- 每个已配置 Server 可启用/停用、编辑、重新发现和删除；
- 发现成功后，工具卡片显示 Server 名称和 `MCP` 标签；
- 选中 MCP Tool 时，右侧详情显示输入参数 Schema；
- “测试调用”要求输入 JSON 对象参数，使用该工具的 Schema 进行提示；
- 连接或调用失败时显示可读错误，不伪装成已接入。

第一版不在对话页自动调用 MCP Tool。工具中心可以验证连接和真实调用，自动路由将在后续作为独立功能设计。

## 错误与安全

- 缺少 `mcp` 依赖：显示“需要安装 MCP 支持”；
- 命令不存在、工作目录无效、启动失败、握手失败、协议错误和工具错误均保留错误信息；
- 未启用的 Server 不参与发现与调用；
- 配置确认页明确提示：该命令会在本机执行，只应添加可信 Server；
- 不包含第三方地址、密钥或自动下载行为。

## 测试

- `MCPServerRegistry` 可新增、更新、删除并持久化配置；
- Client 将 Server 返回的工具定义转换为 LocalMind 工具记录；
- Client 可调用本地测试 MCP Server 并接收文本与结构化结果；
- 不可执行命令与工具返回错误被转换为可读失败结果；
- Tool Registry 同时包含计算器和已发现 MCP Tool；
- Tool Center 只显示真实注册的 MCP Tool，并允许展示其详情。

测试用例不访问网络。端到端测试使用仓库内的最小临时 MCP Server。

## 验收标准

1. 用户能在工具中心添加一个本地 `stdio` MCP Server 配置；
2. 应用能发现该 Server 的工具，并在工具中心标注为 MCP；
3. 用户能在详情页输入参数并成功手动调用测试工具；
4. 配置重启后仍存在；
5. 不可用 Server 与失败工具会显示可读错误；
6. 高级计算器仍可在现有聊天链路中正常使用；
7. 不需要联网即可运行测试。

## 实现状态

首版实现为 LocalMind 的本地 stdio MCP Client：用户在工具中心显式保存可信命令，程序发现 Server 暴露的工具并允许手动传入 JSON 参数测试调用。聊天自动路由、HTTP/SSE transport，以及把 LocalMind 暴露为 MCP Server 均不包含在本版本中。
