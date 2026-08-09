# LocalMind Agent

一个完全本地运行的桌面知识库 Agent。它采用 A「双栏工作台」布局：左侧管理模型、知识库和对话，右侧进行聊天或文档管理。

## 能做什么

- 创建多个独立知识库，例如“人工智能学习”“模电笔记”“项目资料”；
- 上传 TXT、Markdown、PDF、DOCX；
- 使用 `intfloat/multilingual-e5-small` 建立本地向量索引；
- 使用本地 Qwen2.5-1.5B-Instruct 回答问题；
- 对话流式输出，并显示检索到的引用文件；
- 对已启用的本地 MCP Tool 进行一次模型规划、调用和结果总结；
- 对话、原始文件、Embedding、Chroma 和模型缓存都留在本机；
- 通过 `data/state/models.json` 注册后续本地模型。

这里的“文档训练”指把文档解析、切片、向量化并加入 RAG 知识库，不会修改大语言模型参数。

## 第一次运行

在 PowerShell 中执行：

```powershell
cd G:\trial_project\004
python -m venv --system-site-packages .venv_gpu
.\.venv_gpu\Scripts\python.exe -m pip install chromadb sentence-transformers transformers PySide6 PyMuPDF python-docx pytest pyinstaller
.\.venv_gpu\Scripts\python.exe -m app.main
```

也可以直接运行：

```powershell
.\run.ps1
```

`run.ps1` 会优先使用 `.venv_gpu`。本机 RTX 5070 Ti 使用系统中已安装的 CUDA PyTorch；如果不存在 `.venv_gpu`，才回退到 `.venv` CPU 环境。

第一次导入文档或第一次提问时，程序会下载 E5 Embedding 和 Qwen 模型。下载完成后会使用 `data/models` 中的本地缓存。

## 离线运行

确认模型已经下载完成后：

```powershell
$env:LOCAL_AGENT_OFFLINE = "1"
.\run.ps1
```

如果缓存不完整，界面会提示模型加载失败，而不会偷偷调用云端服务。

## 数据目录

```text
data/
├── documents/       # 按知识库保存的原始上传文件
├── chroma_db/       # 持久化向量数据库
├── models/          # E5 和 Qwen 本地模型缓存
└── state/           # 知识库、对话和模型注册表 JSON
```

## 测试

当前 Windows 环境的 pytest 缓存插件会在临时目录触发文件锁，因此测试命令显式关闭 cache provider：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

测试不会下载真实模型。

## 打包

```powershell
.\build.ps1
```

打包结果位于 `dist\LocalMind`。模型不放进安装包，而是在首次使用时下载到 `data\models`，避免安装包达到数 GB。

## 高级计算 Tool

项目现在提供一个独立的本地计算工具，位于 `tools/calculator`。它不调用网络，也不会执行用户输入中的 Python 代码，支持：

- 科学计算：四则运算、括号、幂、百分号、科学计数法、三角函数、对数和指数；
- 单位换算：长度、面积、体积、质量、时间、速度、温度和数据大小；
- 矩阵计算：加减乘、转置、行列式、逆矩阵和线性方程组；
- 符号计算：方程、化简、求导和积分。

直接调用示例：

```python
from tools.calculator.tool import calculator_tool

calculator_tool.run({
    "mode": "arithmetic",
    "expression": "123456789 * 987654321",
})

calculator_tool.run({
    "mode": "unit",
    "value": 5,
    "from_unit": "km",
    "to_unit": "m",
})

calculator_tool.run({
    "mode": "equation",
    "equation": "x**2 - 5*x + 6 = 0",
    "variables": ["x"],
})
```

LocalMind 的对话服务已经接入这个 Tool：对明显的算式、单位换算和方程请求，会先由 `CalculatorRouter` 调用计算器，再把程序验证过的结果交给 Qwen 组织中文回答；普通问题仍然走知识库检索流程。后续如果更换为支持原生 Tool Calling 的模型，可以继续使用 `calculator_tool.schema()` 注册工具。

## MCP 本地接入

LocalMind 可以作为 **MCP Client** 连接你明确配置的本地 `stdio` MCP Server。打开“工具中心”后点击“管理 MCP Server”，填写例如：

```text
名称：本地演示 MCP 服务
命令：python
参数：["-m", "my_mcp_server"]
```

保存时会要求再次确认：该命令仅会在本机执行，请只添加你信任的 Server。保存后，LocalMind 会发现其中公开的工具并显示在工具中心；你可以在右侧填写 JSON 参数并进行手动测试调用。

当前版本只支持本地 `stdio` 连接，不会自动访问 HTTP/SSE Server。聊天中会把已启用且已发现的 MCP Tool 交给本地 LLM 判断；每次问题最多调用一个工具，调用结果会交回模型并显示在聊天记录中。MCP Server 的配置保存在本机 `data/state/mcp_servers.json`，不应提交任何令牌、密码或私密环境变量。
