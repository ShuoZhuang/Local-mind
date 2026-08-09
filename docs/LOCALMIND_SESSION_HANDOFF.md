# LocalMind 会话交接记录

更新时间：2026-08-08

## 1. 项目定位

LocalMind 是一个完全本地运行的桌面知识库 Agent，技术栈为 Python 3.10、PySide6、本地 Qwen2.5-1.5B-Instruct、Sentence Transformer Embedding、Chroma 向量存储和本地工具系统。

项目路径：`G:\trial_project\004`

主要目标：

- 管理多个本地知识库；
- 上传 PDF、DOCX、Markdown、TXT 等文档；
- 解析、分段、向量化并存入 Chroma；
- 对话时检索相关片段并显示回答依据；
- 使用本地 LLM 生成回答；
- 支持本地计算 Tool；
- 支持通过 MCP Client 接入用户明确配置的本地 MCP Server。

## 2. 运行方式

在 PowerShell 中执行：

```powershell
cd G:\trial_project\004
.\run.ps1
```

`run.ps1` 会优先使用：

```text
G:\trial_project\004\.venv_gpu
```

当前机器已验证 GPU：

```text
NVIDIA GeForce RTX 5070 Ti Laptop GPU
CUDA available: True
```

CPU 环境为：

```text
G:\trial_project\004\.venv
```

MCP 已安装到 GPU 环境和 CPU 环境。GPU 环境中的关键依赖包括 `mcp`、`pint`、PyTorch CUDA 版本等。

## 3. 主要目录

```text
004/
├─ app/
│  ├─ main.py
│  ├─ models.py
│  ├─ services/
│  │  ├─ chat.py
│  │  ├─ documents.py
│  │  ├─ embeddings.py
│  │  ├─ ingestion.py
│  │  ├─ llm.py
│  │  ├─ tool_calling.py
│  │  ├─ mcp_client.py
│  │  ├─ storage.py
│  │  ├─ tool_registry.py
│  │  └─ vector_store.py
│  └─ ui/
│     ├─ main_window.py
│     ├─ chat_page.py
│     ├─ knowledge_page.py
│     ├─ tool_center_page.py
│     ├─ mcp_server_dialog.py
│     ├─ workers.py
│     └─ theme.py
├─ data/
│  ├─ documents/
│  ├─ chroma_db/
│  └─ state/
├─ tools/
│  └─ calculator/
├─ tests/
├─ docs/
├─ requirements.txt
├─ config.example.json
└─ run.ps1
```

## 4. 已完成的产品功能

### 4.1 对话

- 支持新建和加载会话；
- 左侧显示最近对话；
- Enter 发送；
- Ctrl+Enter 换行；
- 用户消息和助手消息使用不同气泡；
- 助手回复支持 Markdown 渲染；
- 中间对话区域使用垂直滚动；
- 关闭水平滚动；
- 点击来源可以请求右侧回答依据；
- 可选择多个知识库参与当前对话；
- 支持停止生成；
- 支持启动时预热模型。

### 4.2 知识库

- 支持创建、重命名、删除知识库；
- 删除知识库时清理文档和向量数据；
- 支持文档多选上传；
- 上传后先进入确认界面，不会立即处理；
- 支持自动分段、自定义分段和按层级分段；
- 自定义分段支持多个分隔符预设和自定义分隔符输入；
- 支持设置最大分段长度和重叠长度；
- 支持文档详情页；
- 支持原文预览和分段预览；
- 支持只从检索索引移除单个分块，原始文档仍保留；
- 支持重新处理文档恢复被移除的分块；
- 文档记录以卡片形式展示；
- 支持删除和重新处理文档。

### 4.3 Tool 中心

当前工具中心区分两类内容：

1. 真实可调用工具；
2. 知识库流程使用的本地能力。

已接入的真实工具：

- 高级计算器 `calculator`。

本地能力卡片：

- 文档解析；
- 文本分段；
- Embedding 向量化；
- 知识库检索；
- Chroma 向量存储。

本地能力不是模型可以直接调用的 Tool，只是对内部流程的可视化说明。

已启用并发现的本地 MCP Tool 会通过 `ChatService` 的单次规划流程交给本地 LLM 判断；实际调用仍必须经过 `ToolRegistry` 校验。

### 4.4 高级计算器

位置：`tools/calculator/`

支持：

- 四则运算；
- 三角函数；
- 对数和指数；
- 单位换算；
- 矩阵运算；
- 方程、化简、求导和积分。

对话服务中的明显计算请求会优先经过 `CalculatorRouter`，再把验证后的结果交给 LLM 组织回答。

### 4.5 MCP Client

LocalMind 当前作为 MCP Client 使用，只支持用户明确配置的本地 `stdio` MCP Server。

已经实现：

- `MCPServerDefinition` 配置模型；
- MCP Server 配置持久化到 `data/state/mcp_servers.json`；
- MCP Server 管理对话框；
- 命令、JSON 参数、工作目录和环境变量配置；
- 保存前的本地命令确认；
- 启用/禁用 MCP Server；
- 删除 MCP Server 配置；
- MCP 工具发现；
- MCP 工具统一注册到 `ToolRegistry`；
- MCP 工具在工具中心显示；
- 右侧显示输入 Schema；
- JSON 参数手动测试调用；
- MCP 操作通过 `MCPWorker` 放到后台线程执行；
- 启动时自动发现已启用的 MCP Server。
- 聊天服务把已启用 MCP Tool 的目录交给本地 LLM；
- LLM 输出单次 JSON 工具请求后，由 `ToolRegistry` 校验并调用；
- MCP 结果会回传给 LLM 生成最终 Markdown 回答，并作为工具调用记录保存。

当前明确不包含：

- HTTP/SSE MCP Server；
- Streamable HTTP；
- LocalMind 作为 MCP Server；
- 内置第三方 MCP Server、API Key 或网络服务。

## 5. MCP 配置示例

在工具中心点击“管理 MCP Server”，可以配置：

```text
名称：本地演示 MCP 服务
命令：python
参数：["-m", "my_mcp_server"]
```

参数字段必须是 JSON 字符串数组，例如：

```json
["-m", "tests.mcp_test_server"]
```

环境变量字段必须是 JSON 对象，例如：

```json
{
  "EXAMPLE_MODE": "1"
}
```

## 6. 测试情况

最近一次完整回归：

```text
155 passed
```

使用的测试命令：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider
```

MCP 相关测试包括：

- 本地 stdio MCP Server 工具发现；
- MCP Tool 调用；
- MCP 错误处理；
- MCP 配置持久化；
- ToolRegistry 合并计算器和 MCP 工具；
- MCP Server 管理界面；
- MCP JSON 参数解析；
- LLM MCP 工具调用协议解析；
- ChatService 调用真实本地 stdio MCP Server；
- 工具中心 UI 冒烟测试。

Windows 环境中 pytest cacheprovider 可能因为临时文件锁导致退出异常，所以测试时使用 `-p no:cacheprovider`。

## 7. 当前待办

### 7.1 工具中心筛选分类

用户最新要求：去掉工具中心筛选栏中的：

- 计算；
- 检索；
- 文档。

保留：

- 全部；
- 已启用；
- 本地能力。

该任务已委派给 `luna_worker`，但子智能体因只能写入 `G:\trial_project\001`，无法修改 `G:\trial_project\004`。需要在拥有 004 写权限的会话中完成。

### 7.2 可能的后续增强

- 将 MCP Tool 的调用记录持久化并显示在工具详情页；
- 增加 MCP Server 连接状态和错误详情；
- 支持 HTTP/SSE 或 Streamable HTTP MCP transport；
- 进一步优化工具中心卡片布局和玻璃质感；
- 增加 Tool 配置导入/导出；
- 添加更多本地工具，例如天气、日历、VLR 比赛日程；
- 将天气和 VLR 这类网络能力实现为 MCP Server 后再接入。

## 8. 重要开发约定

- 不要修改 `G:\trial_project\004\data` 中用户已有的知识库数据，除非用户明确要求；
- 不要删除原始文档来实现“移除分块”；移除分块只影响当前检索索引；
- 不要把本地能力伪装成模型可调用工具；
- MCP Server 启动命令必须由用户显式配置和确认；
- 不要把令牌、密码或私密环境变量写入仓库；
- 修改后优先运行针对性测试，再运行完整回归；
- 当前工作区可能存在用户未提交的 UI 修改，修改时需要保留，不要使用 destructive git 命令覆盖。

## 9. 相关提交

MCP 设计和基础实现已形成以下提交：

```text
3bdd535 docs: add MCP client integration design
dc37e98 docs: plan MCP client integration
14e860a feat: persist MCP server configurations
a87137f feat: add stdio MCP client service
```

工具注册表、MCP UI 和文档的后续改动当时保留在工作区中，并与之前的用户 UI 修改混合存在；继续开发前应先查看 `git status` 和 `git diff`，不要覆盖这些未提交改动。
