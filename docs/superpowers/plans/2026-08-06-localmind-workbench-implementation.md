# LocalMind 工作台界面重做 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 LocalMind 改造成统一的深色三栏知识工作台，使对话、知识库、文档导入和引用资料有一致且可验证的交互体验。

**Architecture:** 保持现有 PySide6、后台 Worker、本地模型、Embedding、Chroma 和 LocalStateStore 不变。新增轻量的工作台外壳和右侧上下文面板；ChatPage 与 KnowledgePage 只负责自己的中间主任务，MainWindow 负责把当前会话、当前知识库、文档详情和检索引用分派到正确的视图。

**Tech Stack:** Python 3、PySide6、Qt QPropertyAnimation、pytest、QtTest、现有 Chroma/Sentence Transformers/Transformers 服务。

## Global Constraints

- 保持固定深色主题；禁止白色内容面板，唯一主强调色为薄荷绿。
- 使用 Qt 原生动画，不引入网页 GSAP。
- 后台任务只能经 Worker 信号更新 UI，禁止从 Worker lambda 直接操作控件。
- Enter 发送，Ctrl+Enter 换行。
- 选择文件后必须先确认，才可开始解析、分段、向量化和写入。
- 现有本地数据、知识库、对话和模型配置不得被删除或迁移。
- 项目当前没有 Git 仓库；每个任务以测试通过和手工验证代替提交步骤。

---

## File map

- `app/ui/theme.py`：全局深色设计令牌和控件状态样式。
- `app/ui/workspace.py`：新增三栏工作台外壳、右栏收起按钮和 Qt 动画。
- `app/ui/context_panels.py`：新增聊天引用面板、知识库概览面板和文档详情面板。
- `app/ui/sidebar.py`：重做导航层级、选中状态和列表项上下文菜单外观。
- `app/ui/chat_page.py`：重做消息、输入和生成状态；不再承载引用展示。
- `app/ui/knowledge_page.py`：重做文档列表、导入设置、分块预览与空状态；不再承载完整右侧详情面板。
- `app/ui/main_window.py`：组合工作台，路由页面、文档详情、检索引用、模型准备状态和导入进度。
- `tests/test_ui_smoke.py`：页面结构、交互规则与信号的 UI smoke tests。
- `tests/test_workspace.py`：新增工作台和右栏动画的确定性单元测试。

## Task 1: 建立工作台外壳与右侧上下文容器

**Files:**
- Create: `app/ui/workspace.py`
- Create: `tests/test_workspace.py`
- Modify: `app/ui/main_window.py`

**Interfaces:**
- Produces: `WorkspaceShell(sidebar: QWidget, main: QWidget, context: QWidget)`。
- Produces: `set_main_page(page: QWidget) -> None`、`set_context_page(page: QWidget) -> None`、`set_context_visible(visible: bool) -> None`。
- Emits: `context_visibility_changed(bool)`。

- [ ] **Step 1: 写失败测试，覆盖三栏结构和右栏收起。**

```python
def test_workspace_switches_context_visibility(qapp):
    shell = WorkspaceShell(QWidget(), QWidget(), QWidget())
    assert shell.context_is_visible is True
    shell.set_context_visible(False)
    assert shell.context_is_visible is False
    assert shell.context_container.isHidden()
```

- [ ] **Step 2: 运行测试确认失败。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_workspace.py -q`

Expected: FAIL，因为 `WorkspaceShell` 尚不存在。

- [ ] **Step 3: 实现最小可用工作台。**

```python
class WorkspaceShell(QWidget):
    context_visibility_changed = Signal(bool)

    def set_context_visible(self, visible: bool) -> None:
        self.context_is_visible = visible
        self.context_container.setVisible(visible)
        self.context_visibility_changed.emit(visible)
```

使用 `QSplitter` 管理中间和右侧区域。首次只实现可收起和固定尺寸，动画由 Task 6 加入。

- [ ] **Step 4: 在 MainWindow 中用 WorkspaceShell 替代当前 sidebar + stack 的两栏 splitter。**

`self.stack` 仍保存 ChatPage 与 KnowledgePage；它作为 `WorkspaceShell` 的主区域。右侧先使用空的 `QStackedWidget`，供后续任务填入。

- [ ] **Step 5: 运行相关测试。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_workspace.py tests/test_ui_smoke.py -q`

Expected: PASS。

- [ ] **Step 6: 手工验证。**

启动 `run.ps1`，确认主窗口为左栏、中栏、右栏，右栏收起后中栏变宽。

## Task 2: 固化深色设计令牌并重做侧栏

**Files:**
- Modify: `app/ui/theme.py`
- Modify: `app/ui/sidebar.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Preserves: `Sidebar.activate_chat_context(session_id)` 与 `Sidebar.activate_knowledge_context(knowledge_base_id)`。
- Produces: `Sidebar.active_context_id: str | None`，用于断言只高亮一个列表对象。

- [ ] **Step 1: 写失败测试，保证不会同时选中会话和知识库。**

```python
def test_sidebar_has_only_one_active_context(qapp, state, registry):
    sidebar = Sidebar(state, registry)
    sidebar.activate_chat_context("session-1")
    assert sidebar.active_context_id == "session-1"
    assert sidebar.knowledge_base_list.currentRow() == -1
    sidebar.activate_knowledge_context("kb-1")
    assert sidebar.active_context_id == "kb-1"
    assert sidebar.session_list.currentRow() == -1
```

- [ ] **Step 2: 运行该测试确认它捕获当前行为或失败点。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py::test_sidebar_has_only_one_active_context -q`

- [ ] **Step 3: 在 theme.py 建立语义化样式。**

定义并统一使用：`#10151d` 应用底色、`#161d27` 面板、`#1c2531` 悬浮面板、`#273447` 边框、`#87dfc3` 薄荷绿、`#eaf1f7` 主文字、`#91a0b5` 次文字。列表、输入框、按钮、菜单、滚动条、禁用状态必须覆盖。

- [ ] **Step 4: 重做 Sidebar 布局。**

保留模型选择、对话入口、知识库入口、新建操作、知识库列表、最近对话、右键重命名/删除。把视觉分组改为标题 + 紧凑列表，移除装饰性符号；使用 `QListWidgetItem` 数据保存 id，不能以显示文本定位状态。

- [ ] **Step 5: 运行测试与手工检查。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py -q`

Expected: PASS；手工检查无白色内容面板、切换对象时仅一个项目高亮、右键菜单仍有效。

## Task 3: 重做知识库主区与“确认后处理”的导入抽屉

**Files:**
- Modify: `app/ui/knowledge_page.py`
- Modify: `app/ui/context_panels.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces: `KnowledgeImportPanel`，信号 `confirmed(Path, ChunkingConfig)` 与 `cancelled()`。
- Produces: `DocumentDetailPanel.set_document(record, chunks: list[DocumentChunk]) -> None`。
- Preserves: `KnowledgePage.file_import_requested(Path, object)`、`document_selected(str)`、`document_reprocess_requested(str)`、`document_delete_requested(str)`。

- [ ] **Step 1: 写失败测试，覆盖导入不自动执行和自定义标识符。**

```python
def test_import_panel_requires_confirmation_and_exposes_custom_delimiter(qapp):
    panel = KnowledgeImportPanel()
    panel.set_pending_path(Path("notes.docx"))
    panel.delimiter_combo.setCurrentText("自定义")
    assert panel.custom_delimiter_input.isVisible()
    spy = QSignalSpy(panel.confirmed)
    assert spy.count() == 0
    panel.confirm_button.click()
    assert spy.count() == 1
```

- [ ] **Step 2: 运行测试确认失败。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py::test_import_panel_requires_confirmation_and_exposes_custom_delimiter -q`

- [ ] **Step 3: 将 KnowledgePage 限定为中栏。**

中栏包含知识库标题、文档/分块统计、搜索、添加文档和文档列表。移除中栏里原本重复的文档详情与大段导入配置，把两者转移到右栏面板。

- [ ] **Step 4: 实现右栏导入抽屉与文档详情。**

选择文件后调用 `KnowledgeImportPanel.set_pending_path(path)`，显示文件名、格式、大小和策略。策略支持自动、按层级、自定义；自定义支持九个预设，选择“自定义”时显示输入框。点击确认才发射 `confirmed`，MainWindow 接收后调用既有 `import_file`。

- [ ] **Step 5: 通过 DocumentDetailPanel 展示文档元数据和片段。**

提供“原文预览”和“分块预览”切换；块预览显示序号、文本长度和摘要。没有选中文档时显示可操作空状态。重新处理和删除继续只发射信号，由 MainWindow 保留确认对话与服务调用。

- [ ] **Step 6: 运行测试。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py -q`

Expected: PASS；手工选择文件后不应立刻出现“处理中”。

## Task 4: 重做对话主区并增加真实引用右栏

**Files:**
- Modify: `app/ui/chat_page.py`
- Modify: `app/ui/context_panels.py`
- Modify: `app/ui/main_window.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces: `CitationPanel.set_citations(citations: list[dict]) -> None` 与 `CitationPanel.set_empty_state(reason: str) -> None`。
- Preserves: `ChatPage.send_requested(str)`。
- Produces: `ChatPage.set_generation_active(active: bool)`，在生成时按钮显示“停止生成”。

- [ ] **Step 1: 写失败测试，验证 Enter、Ctrl+Enter 和引用显示。**

```python
def test_chat_citation_panel_shows_actual_sources(qapp):
    panel = CitationPanel()
    panel.set_citations([{"file_name": "学生守则.docx", "score": 0.81, "text": "第一条"}])
    assert "学生守则.docx" in panel.source_list.item(0).text()
    assert "0.81" in panel.source_list.item(0).text()
```

- [ ] **Step 2: 运行测试确认失败。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py::test_chat_citation_panel_shows_actual_sources -q`

- [ ] **Step 3: 将 ChatPage 重做为消息流、输入框和明确的生成状态。**

消息使用角色不同的气泡样式，不以 `QListWidgetItem` 的单行文本拼接展示。输入框提示固定为“Enter 发送，Ctrl+Enter 换行”。生成时保留已输出文本，发送按钮改为“停止生成”，不可再次启动第二个 worker。

- [ ] **Step 4: 在 MainWindow 的 _handle_chat_event 中分发引用。**

当 `event.kind == "citation"` 时，把引用传给 `CitationPanel` 并把右栏切换到引用面板。若 citations 为空，使用 `set_empty_state("未检索到相关资料")`。引用字典需要补充 `text`，因此在 `ChatService._citation` 中添加 `text: hit.text`。

- [ ] **Step 5: 实现新会话标题更新。**

首个用户问题完成后，若当前标题仍为“新对话”，调用 `state.update_session_title(session.id, text[:16])`，刷新侧栏与标题。不得覆盖用户右键手动重命名后的标题。

- [ ] **Step 6: 运行测试。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py -q`

Expected: PASS。

## Task 5: 连接工作台上下文路由与文档详情数据

**Files:**
- Modify: `app/ui/main_window.py`
- Modify: `app/ui/context_panels.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `WorkspaceShell`、`DocumentDetailPanel`、`KnowledgeImportPanel`、`CitationPanel`。
- Produces: `_show_document_context(document_id: str) -> None`、`_show_chat_context(citations: list[dict] | None) -> None`。

- [ ] **Step 1: 写失败测试，验证页面切换时右栏切换到正确上下文。**

```python
def test_knowledge_and_chat_use_different_context_panels(window, record):
    window.open_knowledge_base(record.knowledge_base_id)
    window.open_document_detail(record.id)
    assert window.workspace.context_stack.currentWidget() is window.document_detail_panel
    window.show_chat_page()
    assert window.workspace.context_stack.currentWidget() is window.citation_panel
```

- [ ] **Step 2: 运行测试确认失败。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py::test_knowledge_and_chat_use_different_context_panels -q`

- [ ] **Step 3: 在 MainWindow 组合上下文面板。**

创建一个 `QStackedWidget`，依次添加知识库概览、导入设置、文档详情和对话引用。`show_knowledge_page` 选择知识库概览；`open_document_detail` 读取 Chroma chunks 后填充 DocumentDetailPanel；`show_chat_page` 选择 CitationPanel。

- [ ] **Step 4: 处理无知识库与空知识库。**

无当前知识库时 CitationPanel 显示“未关联知识库”；当前知识库无 ready 文档时显示“这个知识库还没有可检索资料”。不得因为空结果阻止普通模型聊天。

- [ ] **Step 5: 运行测试。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py -q`

Expected: PASS。

## Task 6: 加入可见的后台状态和克制动效

**Files:**
- Modify: `app/ui/workspace.py`
- Modify: `app/ui/main_window.py`
- Modify: `app/ui/context_panels.py`
- Modify: `tests/test_workspace.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces: `WorkspaceShell.set_context_visible(visible: bool, animate: bool = True) -> None`。
- Produces: `ImportProgressPanel.set_stage(stage: str, percent: int, detail: str = "") -> None`。

- [ ] **Step 1: 写失败测试，验证阶段文本与进度更新。**

```python
def test_import_progress_panel_renders_stage(qapp):
    panel = ImportProgressPanel()
    panel.set_stage("生成向量", 60)
    assert panel.stage_label.text() == "生成向量"
    assert panel.progress_bar.value() == 60
```

- [ ] **Step 2: 运行测试确认失败。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_workspace.py::test_import_progress_panel_renders_stage -q`

- [ ] **Step 3: 用 ImportProgressPanel 替换只有单行文字的 QProgressDialog。**

把既有 ingestion stages 映射为：读取文档、提取文本、文本分段、生成向量、写入知识库、完成。失败时面板显示 `DocumentRecord.error`，提供关闭和重新处理入口；成功或失败都自动终止忙碌状态。

- [ ] **Step 4: 为右栏使用 QPropertyAnimation。**

只动画 `maximumWidth` 与 `windowOpacity`，时长分别为 180ms 和 160ms，缓动曲线 `QEasingCurve.OutCubic`。动画结束后再隐藏右栏。没有持续循环动画。

- [ ] **Step 5: 处理模型准备状态。**

在首次聊天或首次向量化之前展示“正在准备本地模型”，禁用会导致重复请求的按钮；模型实例由既有 `_embedding_service` 和 `_llms` 缓存复用。不得在 UI 线程下载或加载模型。

- [ ] **Step 6: 运行全量测试并手工验证。**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; $env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest -q -p no:cacheprovider`

Expected: PASS。手工导入一个小 `.docx`，确认每个阶段可见，窗口可拖动和切页，完成后文档为 ready 或明确 failed。

## Task 7: 完整回归与界面验收

**Files:**
- Modify: `README.md`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Documents: 新的三栏交互、键盘发送规则和导入确认规则。

- [ ] **Step 1: 添加验收型 smoke tests。**

```python
def test_theme_does_not_define_white_content_panel():
    assert "background: #ffffff" not in APP_STYLE.lower()

def test_new_session_title_updates_only_after_first_answer(window):
    window.new_session()
    assert window.current_session.title == "新对话"
```

- [ ] **Step 2: 运行测试确认新增断言有效。**

Run: `$env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest tests/test_ui_smoke.py -q`

- [ ] **Step 3: 更新 README。**

增加“界面使用方式”小节，说明：选择知识库、添加文件后确认处理、Enter/ Ctrl+Enter 行为、回答依据右栏、右键重命名与删除，以及首次模型准备时间。

- [ ] **Step 4: 运行完整测试。**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; $env:QT_QPA_PLATFORM='offscreen'; .\.venv_gpu\Scripts\python.exe -m pytest -q -p no:cacheprovider`

Expected: 全部通过。

- [ ] **Step 5: 手工验收清单。**

1. 无白色内容面板。
2. 左栏只高亮当前会话或知识库。
3. 文件选择后未确认不会处理。
4. 九个分隔符预设与自定义输入框可用。
5. 对话右栏显示实际检索到的片段。
6. 导入成功、失败和空状态都有可理解说明。
7. 重复打开已加载模型不会再次长时间加载。

## Plan self-review

- Spec coverage: 全局三栏、深色主题、知识库导入、分段策略、文档详情、对话引用、加载/失败状态、动效和验收标准均有对应任务。
- Placeholder scan: 计划中没有未落实的占位内容或模糊的后续工作描述。
- Type consistency: `WorkspaceShell`、`CitationPanel`、`KnowledgeImportPanel`、`DocumentDetailPanel` 的职责、入口和 MainWindow 调用关系在各任务中保持一致。
