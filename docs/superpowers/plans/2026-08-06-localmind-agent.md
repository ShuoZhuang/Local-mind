# LocalMind Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `G:\trial_project\004` 构建一个完全本地运行的 Windows 桌面 Agent，支持多知识库、多本地模型、可保存对话、文档检索和带引用的流式回答。

**Architecture:** 使用 PySide6 构建 A「双栏工作台」桌面界面；文档经过解析、切片和 E5 Embedding 后按知识库写入独立的 Chroma collection；问题检索当前知识库后交给本地 Qwen 模型流式生成。模型通过注册表配置，首版使用 Transformers 从 Hugging Face 首次下载并缓存到本机，后续离线加载。

**Tech Stack:** Python 3.11+, PySide6, sentence-transformers, ChromaDB, Transformers, PyTorch, PyMuPDF, python-docx, pytest, PyInstaller。

## Global Constraints

- 新项目根目录固定为 `G:\trial_project\004`；不得修改 `G:\trial_project\001`。
- 不调用 OpenAI 或其他云端大模型 API，不要求 API Key。
- 首次运行允许下载模型；模型缓存、原始文档、向量库、聊天记录全部保存在本机。
- “文档训练”实现为 RAG 知识库索引，不对 Qwen 参数做微调。
- 默认模型为 `Qwen/Qwen2.5-1.5B-Instruct`；默认 Embedding 为 `intfloat/multilingual-e5-small`。
- 默认支持 TXT、Markdown、PDF、DOCX；空文件、不支持的扩展名和解析失败必须在界面中显示可理解的错误。
- UI 必须保持 A 双栏工作台：左栏导航/模型/知识库/对话历史，右栏对话或知识库管理页面。
- 测试不得下载或加载真实大模型；使用 fake embedding、fake LLM 和临时 Chroma 目录。

---

### Task 1: 项目骨架、配置和领域数据结构

**Files:**
- Create: `G:\trial_project\004\app\__init__.py`
- Create: `G:\trial_project\004\app\config.py`
- Create: `G:\trial_project\004\app\models.py`
- Create: `G:\trial_project\004\app\main.py`
- Create: `G:\trial_project\004\requirements.txt`
- Create: `G:\trial_project\004\run.ps1`
- Create: `G:\trial_project\004\tests\test_models.py`

**Interfaces:**
- `AppConfig.from_root(root: Path) -> AppConfig` 返回数据、模型和 Chroma 路径。
- `KnowledgeBase(id: str, name: str, description: str, created_at: str) -> dataclass`。
- `ChatSession(id: str, title: str, knowledge_base_id: str, model_id: str, created_at: str, updated_at: str) -> dataclass`。
- `ChatMessage(role: Literal["user", "assistant"], content: str, citations: list[dict]) -> dataclass`。
- `ModelDefinition(id: str, display_name: str, model_name: str, local_path: str | None, provider: str) -> dataclass`。
- `SearchHit(id: str, text: str, score: float, metadata: dict) -> dataclass`。

- [ ] **Step 1: 写领域对象的失败测试**

```python
def test_chat_session_has_knowledge_base_and_model():
    session = ChatSession.new("kb-ai", "qwen-1.5b")
    assert session.knowledge_base_id == "kb-ai"
    assert session.model_id == "qwen-1.5b"
    assert session.title == "新对话"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_models.py -q`
Expected: FAIL，因为 `app.models` 尚未定义。

- [ ] **Step 3: 实现 dataclass 和配置**

实现 `ChatSession.new()`、`KnowledgeBase.new()`、`AppConfig.from_root()`；配置默认创建 `data/documents`、`data/chroma_db`、`data/models`、`data/state` 路径，并把模型定义加载到 `data/state/models.json`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_models.py -q`
Expected: PASS。

- [ ] **Step 5: 增加启动脚本并做导入检查**

`run.ps1` 激活 `\.venv\Scripts\python.exe` 后执行 `python -m app.main`；没有虚拟环境时显示创建和安装依赖命令，而不是静默失败。

Run: `python -c "from app.config import AppConfig; from app.models import ChatSession; print('ok')"`
Expected: 输出 `ok`。

---

### Task 2: 本地状态存储、多知识库和对话历史

**Files:**
- Create: `G:\trial_project\004\app\services\storage.py`
- Modify: `G:\trial_project\004\app\models.py`
- Create: `G:\trial_project\004\tests\test_storage.py`

**Interfaces:**
- `LocalStateStore(root: Path)`。
- `create_knowledge_base(name: str, description: str) -> KnowledgeBase`。
- `list_knowledge_bases() -> list[KnowledgeBase]`。
- `delete_knowledge_base(knowledge_base_id: str) -> None`。
- `save_session(session: ChatSession, messages: list[ChatMessage]) -> None`。
- `list_sessions() -> list[ChatSession]`。
- `load_session(session_id: str) -> tuple[ChatSession, list[ChatMessage]]`。
- `update_session_title(session_id: str, title: str) -> None`。

- [ ] **Step 1: 写状态持久化失败测试**

测试新建三个知识库后列表保持顺序；保存带一条用户消息和一条助手消息的会话；重新实例化 `LocalStateStore` 后仍可读取；删除知识库后其状态不再出现在列表中。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_storage.py -q`
Expected: FAIL，因为存储实现尚不存在。

- [ ] **Step 3: 实现原子 JSON 存储**

使用 `knowledge_bases.json`、`sessions.json` 和 `session_<id>.json`；写入时先写临时文件再替换目标文件，避免应用关闭时产生半份 JSON。保存时间使用 ISO 8601 字符串；读取损坏文件时返回空初始状态并保留 `.broken` 备份。

- [ ] **Step 4: 实现知识库和会话删除/更新**

知识库删除只负责本地状态层，向量 collection 和文件删除由后续 `KnowledgeBaseService` 调用，以保持存储模块单一职责。

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_storage.py -q`
Expected: PASS。

---

### Task 3: 文档解析、切片和多知识库文件管理

**Files:**
- Create: `G:\trial_project\004\app\services\documents.py`
- Create: `G:\trial_project\004\tests\test_documents.py`

**Interfaces:**
- `SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}`。
- `extract_text(path: Path) -> list[tuple[int | None, str]]`：返回页码和文本块。
- `chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]`。
- `DocumentIngestor(root: Path)`。
- `ingest(path: Path, knowledge_base_id: str) -> list[DocumentChunk]`。
- `DocumentChunk(id: str, text: str, metadata: dict)`；metadata 必须含 `knowledge_base_id`, `source`, `file_name`, `chunk_index`，PDF 额外含 `page`。

- [ ] **Step 1: 写文本切片和解析失败测试**

覆盖：短文本只产生一个片段；长文本片段之间有重叠词；空文本抛出 `ValueError`；不支持扩展名抛出 `UnsupportedDocumentError`；同一文件重复导入产生相同文档哈希和稳定 chunk ID。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_documents.py -q`
Expected: FAIL，因为解析器尚不存在。

- [ ] **Step 3: 实现 TXT/Markdown 解析**

使用 UTF-8、GB18030、UTF-8 BOM 依次尝试；Markdown 保留正文文本，去掉 front matter 和代码围栏标记但不删除代码内容。

- [ ] **Step 4: 实现 PDF/DOCX 解析**

使用 PyMuPDF 逐页读取 PDF；使用 `python-docx` 按段落读取 DOCX；所有解析结果统一为 `(page, text)`，非 PDF 页码为 `None`。

- [ ] **Step 5: 实现按知识库隔离的原始文件复制**

复制到 `data/documents/<knowledge_base_id>/<sha256>_<safe_file_name>`，保留原文件名元数据；同一哈希不重复复制。

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_documents.py -q`
Expected: PASS。

---

### Task 4: E5 Embedding、Chroma collection 和检索服务

**Files:**
- Create: `G:\trial_project\004\app\services\embeddings.py`
- Create: `G:\trial_project\004\app\services\vector_store.py`
- Create: `G:\trial_project\004\app\services\retrieval.py`
- Create: `G:\trial_project\004\tests\test_retrieval.py`

**Interfaces:**
- `EmbeddingService(model_name: str, cache_folder: Path, device: str = "auto")`。
- `encode_query(text: str) -> list[float]`。
- `encode_documents(texts: list[str]) -> list[list[float]]`。
- `KnowledgeBaseVectorStore(db_path: Path, knowledge_base_id: str)`。
- `upsert(chunks: list[DocumentChunk], vectors: list[list[float]]) -> None`。
- `delete_document(document_hash: str) -> None`。
- `count() -> int`。
- `query(vector: list[float], top_k: int = 5) -> list[SearchHit]`。
- `RetrievalService.search(knowledge_base_id: str, query: str, top_k: int = 5) -> list[SearchHit]`。

- [ ] **Step 1: 写 fake backend 检索失败测试**

用固定二维向量写入两个知识库，验证查询只返回当前知识库 collection；结果按 score 降序，分数相同时按 chunk ID 稳定排序；`top_k <= 0` 返回空列表。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_retrieval.py -q`
Expected: FAIL，因为 vector store 和 retrieval 尚不存在。

- [ ] **Step 3: 实现 E5 wrapper**

统一在内部添加一次 `query:` 与 `passage:` 前缀，并用 `normalize_embeddings=True` 输出；不向调用方暴露前缀细节。`device="auto"` 时优先 CUDA，否则 CPU。

- [ ] **Step 4: 实现 Chroma collection 隔离**

collection 名称使用 `kb_<knowledge_base_id>`，记录 ID 使用稳定 chunk ID；写入文档、向量和 metadata；查询返回 Chroma distance 转换后的 similarity 字段，但 UI 同时标注“仅用于排序”。

- [ ] **Step 5: 实现导入编排服务**

`KnowledgeBaseService.import_file()` 负责解析、切片、批量 embedding、upsert；每一步通过 callback 报告 `extracting`, `embedding`, `saving`, `done` 和进度百分比，失败时不保存未完成批次。

- [ ] **Step 6: 运行单元测试和 fake 流程**

Run: `python -m pytest tests/test_retrieval.py -q`
Expected: PASS；测试只使用临时目录和 fake vectors，不触发模型下载。

---

### Task 5: 可切换本地 Qwen 模型和 RAG 对话服务

**Files:**
- Create: `G:\trial_project\004\app\services\model_registry.py`
- Create: `G:\trial_project\004\app\services\llm.py`
- Create: `G:\trial_project\004\app\services\chat.py`
- Create: `G:\trial_project\004\tests\test_chat.py`

**Interfaces:**
- `ModelRegistry(state_path: Path)`。
- `list_models() -> list[ModelDefinition]`。
- `add_model(definition: ModelDefinition) -> None`。
- `get(model_id: str) -> ModelDefinition`。
- `LocalLLM(model: ModelDefinition, cache_dir: Path)`。
- `is_loaded() -> bool`。
- `load(progress_callback: Callable[[str], None] | None = None) -> None`。
- `generate_stream(messages: list[dict], max_new_tokens: int = 512) -> Iterator[str]`。
- `ChatService.answer(query: str, knowledge_base_id: str, model_id: str, history: list[ChatMessage]) -> Iterator[ChatEvent]`。
- `ChatEvent(kind: Literal["status", "token", "citation", "done", "error"], payload: object)`。

- [ ] **Step 1: 写 fake LLM 的 RAG 编排失败测试**

给 fake retrieval 返回一条来源，给 fake LLM 返回固定 token 流；验证 prompt 同时包含用户问题、检索文本和“只根据资料回答”的规则；验证 citation event 在 done 前产生；没有命中时 prompt 明确告知模型资料不足。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chat.py -q`
Expected: FAIL，因为 chat service 尚不存在。

- [ ] **Step 3: 实现模型注册表**

初始化默认条目：

```json
{
  "id": "qwen2.5-1.5b",
  "display_name": "Qwen2.5 1.5B",
  "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
  "local_path": null,
  "provider": "transformers"
}
```

后续新增模型只添加同结构 JSON 条目；UI 不写死模型名称。

- [ ] **Step 4: 实现 Transformers 本地推理**

使用 `AutoTokenizer`、`AutoModelForCausalLM` 和 `TextIteratorStreamer`；模型在独立 worker 线程中加载和生成；检测 `torch.cuda.is_available()` 后选择 CUDA 或 CPU；模型缓存位置为 `data/models`。首次下载失败时返回可读错误，后续可从缓存离线加载。

- [ ] **Step 5: 实现 RAG prompt 和引用事件**

prompt 包含系统规则、最多 5 个检索片段、用户问题；每个片段带 `[来源 N]` 标识。回答后把实际检索命中的元数据转换为 citation event，UI 展示文件名和页码。

- [ ] **Step 6: 运行 fake chat 测试确认通过**

Run: `python -m pytest tests/test_chat.py -q`
Expected: PASS；不得实例化真实 Transformers 模型。

---

### Task 6: PySide6 双栏工作台和知识库管理界面

**Files:**
- Create: `G:\trial_project\004\app\ui\main_window.py`
- Create: `G:\trial_project\004\app\ui\sidebar.py`
- Create: `G:\trial_project\004\app\ui\chat_page.py`
- Create: `G:\trial_project\004\app\ui\knowledge_page.py`
- Create: `G:\trial_project\004\app\ui\workers.py`
- Create: `G:\trial_project\004\app\ui\theme.py`
- Modify: `G:\trial_project\004\app\main.py`
- Create: `G:\trial_project\004\tests\test_ui_smoke.py`

**Interfaces:**
- `MainWindow(config: AppConfig, state: LocalStateStore, services: ServiceContainer)`。
- `Sidebar.knowledge_base_selected = Signal(str)`。
- `Sidebar.model_selected = Signal(str)`。
- `Sidebar.new_session_requested = Signal()`。
- `ChatPage.send_requested = Signal(str)`。
- `KnowledgePage.file_import_requested = Signal(Path)`。
- `KnowledgePage.import_progress = Signal(str, int)`。

- [ ] **Step 1: 写 UI smoke test**

在 `QT_QPA_PLATFORM=offscreen` 下创建 QApplication 和 MainWindow，验证窗口含左侧知识库列表、模型下拉框、对话页、知识库页；点击新建对话后左侧会话列表数量增加。

- [ ] **Step 2: 运行测试确认失败**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_ui_smoke.py -q`
Expected: FAIL，因为 UI 类尚不存在。

- [ ] **Step 3: 实现主题和主窗口布局**

使用固定左栏宽度约 292px、右栏自适应；深色配色、圆角卡片、绿色强调色；右侧使用 `QStackedWidget` 在聊天页和知识库管理页之间切换。

- [ ] **Step 4: 实现 Sidebar**

显示当前模型下拉框、对话列表、多个知识库栏目、新建对话和新建知识库按钮；切换知识库只更新当前上下文，不删除其他 collection。

- [ ] **Step 5: 实现 ChatPage**

显示消息气泡、流式 token 追加、生成状态、停止按钮、引用卡片；新建对话创建 `ChatSession` 并立即显示在左栏；发送后保存用户和助手消息。

- [ ] **Step 6: 实现 KnowledgePage**

显示当前知识库统计、文件选择/拖拽入口、文档列表、切片数、处理状态和删除操作；导入任务运行在 worker 线程，界面只通过信号更新进度。

- [ ] **Step 7: 运行 UI smoke test 确认通过**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_ui_smoke.py -q`
Expected: PASS。

---

### Task 7: 启动体验、文档说明和桌面打包

**Files:**
- Create: `G:\trial_project\004\README.md`
- Create: `G:\trial_project\004\config.example.json`
- Create: `G:\trial_project\004\build.ps1`
- Create: `G:\trial_project\004\.gitignore`
- Modify: `G:\trial_project\004\run.ps1`

- [ ] **Step 1: 写启动和离线模式检查**

启动时显示模型状态：未下载、下载中、已缓存、加载失败；设置 `LOCAL_AGENT_OFFLINE=1` 时禁止网络下载并直接使用缓存，缺失模型时在窗口显示解决办法。

- [ ] **Step 2: 写 README 使用流程**

文档包含：创建虚拟环境、安装依赖、首次启动模型下载、离线启动、创建知识库、导入文档、新建对话、切换模型和数据目录说明；明确说明知识库索引不是微调训练。

- [ ] **Step 3: 配置 PyInstaller**

`build.ps1` 执行 `pyinstaller --noconfirm --windowed --name LocalMind app/main.py`，把 `data` 目录作为外置数据目录；模型不打进安装包，首次运行下载到 `data/models`，避免生成数 GB 的安装包。

- [ ] **Step 4: 运行完整测试**

Run: `python -m pytest -q`
Expected: 所有单元测试和 UI smoke test PASS，且没有真实模型下载。

- [ ] **Step 5: 做手动验收**

从 `G:\trial_project\004` 启动：创建三个知识库、导入 TXT 和 Markdown、重启确认数据存在、新建两条对话、切换模型条目、查询并确认引用显示；最后执行 PyInstaller 构建并启动生成的桌面程序。

## Self-Review Checklist

- 多知识库：Task 2、Task 4、Task 6 覆盖独立状态、collection 和切换界面。
- 多模型：Task 5、Task 6、Task 7 覆盖注册表、下拉切换、缓存加载和离线状态。
- 对话历史：Task 2、Task 6 覆盖创建、保存、重新打开和左侧显示。
- 文档上传：Task 3、Task 4、Task 6 覆盖四种格式、切片、Embedding、Chroma 和进度。
- 本地运行：Global Constraints、Task 5、Task 7 明确没有 API Key 和离线行为。
- 测试隔离：所有测试使用 fake 服务或临时目录，不下载模型。
- 依赖一致性：后续任务使用的 `KnowledgeBase`, `ChatSession`, `SearchHit`, `ChatEvent` 和服务方法均已在前置任务中定义。
- 未使用 TBD、TODO、placeholder 或未定义的接口。
