# 可检索分块删除与技能中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许用户从检索知识库中移除单个分块、修正右侧栏箭头方向，并提供一个诚实的空技能中心。

**Architecture:** 在 `KnowledgeBaseVectorStore` 添加按分块 ID 删除的最小接口；`MainWindow` 负责确认、删除、保存文档计数并刷新详情。文档详情面板只发出删除请求，不直接访问存储。技能中心沿用工具中心的三栏工作区结构，但第一版只显示空状态。

**Tech Stack:** Python 3.10、PySide6、ChromaDB、pytest。

## Global Constraints

- 删除单个分块只能影响向量库和检索结果，不能删除原始文件。
- 删除失败时不得修改 `DocumentRecord.chunk_count`。
- 重新处理已有文档必须从原始文件恢复完整分块集。
- 技能中心第一版不得声明或展示不存在的技能。
- 所有 UI 复制文本使用中文，并沿用深色玻璃主题。

---

### Task 1: 向量库按分块删除接口

**Files:**

- Modify: `app/services/vector_store.py:37-57`
- Test: `tests/test_vector_store.py`

**Interfaces:**

- Produces: `KnowledgeBaseVectorStore.delete_chunk(chunk_id: str) -> bool`
- Consumes: 已存在的 Chroma collection 和分块 `id`。

- [ ] **Step 1: 写失败测试**

```python
def test_delete_chunk_removes_only_requested_vector(tmp_path):
    store = KnowledgeBaseVectorStore(tmp_path, "kb-test")
    chunks = [
        DocumentChunk("chunk-1", "第一段", {"document_id": "doc-1", "chunk_index": 0}),
        DocumentChunk("chunk-2", "第二段", {"document_id": "doc-1", "chunk_index": 1}),
    ]
    store.upsert(chunks, [[1.0, 0.0], [0.0, 1.0]])

    assert store.delete_chunk("chunk-1") is True
    assert [chunk.id for chunk in store.get_document_chunks("doc-1")] == ["chunk-2"]
    assert store.delete_chunk("missing") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest -q tests/test_vector_store.py::test_delete_chunk_removes_only_requested_vector`

Expected: FAIL，提示 `KnowledgeBaseVectorStore` 没有 `delete_chunk`。

- [ ] **Step 3: 实现最小接口**

```python
def delete_chunk(self, chunk_id: str) -> bool:
    found = self.collection.get(ids=[chunk_id])
    if not found.get("ids"):
        return False
    self.collection.delete(ids=[chunk_id])
    return True
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest -q tests/test_vector_store.py::test_delete_chunk_removes_only_requested_vector`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/services/vector_store.py tests/test_vector_store.py
git commit -m "feat: delete individual knowledge chunks"
```

### Task 2: 文档详情右键菜单与删除信号

**Files:**

- Modify: `app/ui/context_panels.py:279-320`
- Test: `tests/test_workspace.py`

**Interfaces:**

- Produces: `DocumentDetailPanel.chunk_delete_requested = Signal(str, str)`，参数依次为文档 ID、分块 ID。
- Consumes: `DocumentChunk.id` 和 `DocumentDetailPanel._document_id`。

- [ ] **Step 1: 写失败测试**

```python
def test_document_detail_panel_emits_chunk_delete_request_from_context_menu():
    panel = DocumentDetailPanel()
    record = DocumentRecord.new("kb-1", "讲义.docx", "hash", ChunkingConfig())
    panel.set_document(record, [DocumentChunk("chunk-1", "第一段")])
    spy = QSignalSpy(panel.chunk_delete_requested)

    menu = panel.chunk_context_menu_for_row(0)
    action = next(action for action in menu.actions() if action.text() == "从知识库移除")
    action.trigger()

    assert spy.count() == 1
    assert spy.at(0)[0] == record.id
    assert spy.at(0)[1] == "chunk-1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest -q tests/test_workspace.py::test_document_detail_panel_emits_chunk_delete_request_from_context_menu`

Expected: FAIL，提示缺少 `chunk_context_menu_for_row` 或 `chunk_delete_requested`。

- [ ] **Step 3: 实现右键菜单**

```python
self.chunk_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self.chunk_list.customContextMenuRequested.connect(self._show_chunk_menu)

def chunk_context_menu_for_row(self, row: int) -> QMenu:
    item = self.chunk_list.item(row)
    menu = QMenu(self)
    if item is None or not self._document_id:
        return menu
    action = menu.addAction("从知识库移除")
    chunk_id = str(item.data(Qt.ItemDataRole.UserRole))
    action.triggered.connect(
        lambda: self.chunk_delete_requested.emit(self._document_id, chunk_id)
    )
    return menu
```

在 `set_document` 中将 `chunk.id` 存入 `Qt.ItemDataRole.UserRole`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest -q tests/test_workspace.py::test_document_detail_panel_emits_chunk_delete_request_from_context_menu`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/ui/context_panels.py tests/test_workspace.py
git commit -m "feat: expose chunk removal from document preview"
```

### Task 3: 主窗口删除协调与可恢复计数

**Files:**

- Modify: `app/ui/main_window.py:110-125, 331-350`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**

- Consumes: `DocumentDetailPanel.chunk_delete_requested(document_id, chunk_id)` 和 `KnowledgeBaseVectorStore.delete_chunk(chunk_id)`。
- Produces: `MainWindow.delete_chunk_from_knowledge_base(document_id: str, chunk_id: str) -> None`。

- [ ] **Step 1: 写失败测试**

```python
def test_main_window_removes_chunk_without_deleting_source_document(tmp_path, monkeypatch):
    window, record = build_window_with_document(tmp_path, chunk_count=2)
    store = FakeStore(delete_result=True, remaining_chunks=1)
    monkeypatch.setattr(window, "_store_factory", lambda _kb_id: store)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)

    window.delete_chunk_from_knowledge_base(record.id, "chunk-1")

    assert store.deleted_chunk_ids == ["chunk-1"]
    assert window.state.get_document(record.id).chunk_count == 1
    assert Path(record.source_path).exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest -q tests/test_ui_smoke.py::test_main_window_removes_chunk_without_deleting_source_document`

Expected: FAIL，提示缺少 `delete_chunk_from_knowledge_base`。

- [ ] **Step 3: 实现确认与刷新逻辑**

```python
def delete_chunk_from_knowledge_base(self, document_id: str, chunk_id: str) -> None:
    record = self.state.get_document(document_id)
    answer = QMessageBox.question(
        self, "从知识库移除分块",
        "这会让该分块不再参与检索。原始文档会保留，可通过“重新处理”恢复。是否继续？",
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    store = self._store_factory(record.knowledge_base_id)
    if not store.delete_chunk(chunk_id):
        self._show_error("未找到该分块，未进行删除。")
        return
    record.chunk_count = len(store.get_document_chunks(record.id))
    self.state.save_document(record)
    self.open_document_detail(record.id)
    self.knowledge_page.set_documents(self.state.list_documents(record.knowledge_base_id))
```

连接 `self.document_detail_panel.chunk_delete_requested` 到该方法。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest -q tests/test_ui_smoke.py::test_main_window_removes_chunk_without_deleting_source_document`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/ui/main_window.py tests/test_ui_smoke.py
git commit -m "feat: remove chunks from retrieval without deleting source"
```

### Task 4: 修正右侧栏边缘箭头状态

**Files:**

- Modify: `app/ui/workspace.py:42-117`
- Test: `tests/test_workspace.py`

**Interfaces:**

- Produces: 展开状态显示 `›`，收起状态显示 `‹` 的 `context_expand_button`。

- [ ] **Step 1: 写失败测试**

```python
def test_workspace_edge_arrow_points_to_the_next_context_state():
    shell = WorkspaceShell(QWidget(), QWidget(), QWidget())
    assert shell.context_expand_button.text() == "›"
    shell.set_context_visible(False, animate=False)
    assert shell.context_expand_button.text() == "‹"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest -q tests/test_workspace.py::test_workspace_edge_arrow_points_to_the_next_context_state`

Expected: FAIL，当前箭头文案相反。

- [ ] **Step 3: 交换状态文案与悬停提示**

```python
self.context_expand_button.setText("›" if visible else "‹")
self.context_expand_button.setToolTip("收起回答依据" if visible else "展开回答依据")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest -q tests/test_workspace.py::test_workspace_edge_arrow_points_to_the_next_context_state`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/ui/workspace.py tests/test_workspace.py
git commit -m "fix: correct context rail arrow direction"
```

### Task 5: 新增技能中心空状态页面

**Files:**

- Create: `app/ui/skills_center_page.py`
- Modify: `app/ui/sidebar.py:18-160`
- Modify: `app/ui/main_window.py:67-175`
- Modify: `app/ui/theme.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**

- Produces: `SkillsCenterPage` 和 `SkillsOverviewPanel`。
- Produces: `Sidebar.skill_page_requested = Signal()` 与 `Sidebar.activate_skill_context()`。
- Consumes: `MainWindow.show_skills_page()`，将中部堆栈切换到 `SkillsCenterPage`、右侧堆栈切换到 `SkillsOverviewPanel`。

- [ ] **Step 1: 写失败测试**

```python
def test_skills_button_opens_honest_empty_skills_center(tmp_path):
    window = build_window(tmp_path)
    window.sidebar.skill_button.click()

    assert window.stack.currentWidget() is window.skills_center_page
    assert window.context_stack.currentWidget() is window.skills_overview_panel
    assert "尚未添加技能" in window.skills_center_page.empty_title.text()
    assert window.sidebar.skill_button.property("active") is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest -q tests/test_ui_smoke.py::test_skills_button_opens_honest_empty_skills_center`

Expected: FAIL，提示缺少技能中心属性。

- [ ] **Step 3: 实现页面与导航**

```python
class SkillsCenterPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.empty_title = QLabel("尚未添加技能")
        self.empty_detail = QLabel(
            "技能用于定义 AI 的工作流程；未来可结合工具和知识库执行复杂任务。"
        )
```

在 `Sidebar` 中新增 `skill_button = QPushButton("✦ 技能")`，与现有导航按钮采用相同的 `SidebarNav` 样式和活动态管理。`MainWindow` 创建并加入两个 stacked widget，连接 `skill_page_requested` 到 `show_skills_page()`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest -q tests/test_ui_smoke.py::test_skills_button_opens_honest_empty_skills_center`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/ui/skills_center_page.py app/ui/sidebar.py app/ui/main_window.py app/ui/theme.py tests/test_ui_smoke.py
git commit -m "feat: add empty skills center"
```

### Task 6: 回归验证

**Files:**

- Test: `tests/test_vector_store.py`
- Test: `tests/test_workspace.py`
- Test: `tests/test_ui_smoke.py`
- Test: `tests/test_tool_center.py`

**Interfaces:**

- Consumes: Tasks 1-5 的全部公开接口。
- Produces: 可复现的回归验证记录。

- [ ] **Step 1: 运行目标测试集**

Run: `python -m pytest -q tests/test_vector_store.py tests/test_workspace.py tests/test_ui_smoke.py tests/test_tool_center.py`

Expected: 所有测试通过。

- [ ] **Step 2: 运行离屏主窗口烟测**

```powershell
.\.venv\Scripts\python.exe -c "import os; os.environ['QT_QPA_PLATFORM']='offscreen'; from app.main import build_window; from pathlib import Path; import tempfile; window = build_window(Path(tempfile.mkdtemp())); window.sidebar.skill_button.click(); assert '尚未添加技能' in window.skills_center_page.empty_title.text(); print('UI smoke: PASS')"
```

Expected: 输出 `UI smoke: PASS`。

- [ ] **Step 3: 检查改动与提交**

Run: `git diff --check && git status --short`

Expected: 无空白错误；仅出现本计划相关文件。

- [ ] **Step 4: 提交回归验证后的剩余改动**

```bash
git add app/ui app/services tests
git commit -m "test: verify chunk removal and skills center"
```
