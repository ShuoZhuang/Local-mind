# 对话知识库选择与证据联动 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** 为 LocalMind 对话工作台增加当前会话的多知识库选择、来源到回答依据的联动，以及不带气泡背景的工具调用记录。

**Architecture:** 保留现有 PySide6 三栏结构。会话新增 \`knowledge_base_ids\` 并兼容旧的单 ID；检索层新增多库合并接口，ChatService 接收选择列表并生成带知识库信息的 citations；ChatPage 负责选择菜单、可点击来源行和透明工具行，MainWindow 负责会话状态、检索和右侧面板联动。

**Tech Stack:** Python 3.10+, PySide6, Chroma, pytest, Qt signals/slots, QMenu/QAction；不新增 React、GSAP 或网络服务依赖。

## Global Constraints

- 知识库选择作用域是当前会话，不改变全局默认知识库。
- 必须兼容只包含 \`knowledge_base_id\` 的旧会话 JSON。
- 多库检索只使用当前勾选的知识库，结果按相似度降序并以 ID 稳定打破同分。
- 来源行点击后只显示对应回复的 citations。
- 工具调用不得使用 \`UserBubble\`、\`AssistantBubble\` 或带圆角填充背景的气泡样式。
- 不引入 React、GSAP 或新的运行时依赖。
- 每个生产行为变更都必须先有会失败的测试，再写实现代码。
- 完成前必须运行完整测试，并检查 \`git diff --check\`。

---

### Task 1: 会话模型与本地持久化的多知识库兼容

**Files:**
- Modify: \`app/models.py: ChatSession\`
- Modify: \`app/services/storage.py: session save/load helpers\`
- Test: \`tests/test_models.py\`
- Test: \`tests/test_storage.py\`

**Interfaces:**
- \`ChatSession\` 增加 \`knowledge_base_ids: list[str]\`，默认值为空列表以保持 dataclass 字段顺序合法。
- \`ChatSession.new(knowledge_base_id, model_id)\` 同时填充旧字段和单元素 \`knowledge_base_ids\`。
- \`ChatSession.selected_knowledge_base_ids() -> list[str]\` 返回去重、保序、非空的选择列表；空列表回退到 \`knowledge_base_id\`。
- \`ChatSession.set_knowledge_base_ids(ids: list[str]) -> None\` 清洗 ID，并把第一个 ID 同步到旧字段 \`knowledge_base_id\`。
- \`ChatSession.from_dict()\` 读取新字段；缺失时从旧 \`knowledge_base_id\` 构造单元素列表。

- [ ] **Step 1: Write the failing tests**

\`\`\`python
def test_chat_session_round_trips_multiple_knowledge_bases():
    session = ChatSession.new("kb-one", "qwen-1.5b")
    session.set_knowledge_base_ids(["kb-two", "kb-one", "kb-two"])

    restored = ChatSession.from_dict(session.to_dict())

    assert restored.selected_knowledge_base_ids() == ["kb-two", "kb-one"]
    assert restored.knowledge_base_id == "kb-two"


def test_chat_session_reads_legacy_single_knowledge_base_json():
    restored = ChatSession.from_dict({
        "id": "session-old",
        "title": "旧会话",
        "knowledge_base_id": "kb-old",
        "model_id": "qwen-1.5b",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    })

    assert restored.selected_knowledge_base_ids() == ["kb-old"]
\`\`\`

- [ ] **Step 2: Run tests to verify they fail**

Run:

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_models.py -k "multiple_knowledge_bases or legacy_single" -v
\`\`\`

Expected: FAIL because \`ChatSession\` has no multi-ID field or compatibility helper.

- [ ] **Step 3: Write minimal implementation**

Add the field and helpers exactly as specified. Keep \`knowledge_base_id\` in serialized output so old callers and existing tests continue to work. Do not change unrelated storage formats.

- [ ] **Step 4: Run tests to verify they pass**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_models.py tests/test_storage.py -v
\`\`\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add app/models.py app/services/storage.py tests/test_models.py tests/test_storage.py
git commit -m "feat: persist multi knowledge base chat selection"
\`\`\`

### Task 2: 多知识库检索与引用元数据

**Files:**
- Modify: \`app/services/retrieval.py: RetrievalService\`
- Modify: \`app/services/chat.py: ChatService.answer and citation helpers\`
- Test: \`tests/test_retrieval.py\`
- Test: \`tests/test_chat.py\`

**Interfaces:**
- Add \`RetrievalService.search_many(knowledge_base_ids: Iterable[str], query: str, top_k: int = 5) -> list[SearchHit]\`.
- Keep \`RetrievalService.search(knowledge_base_id: str, query: str, top_k: int = 5)\` as a one-ID wrapper around \`search_many\`.
- \`search_many\` encodes the query once, queries each non-empty selected store, adds \`knowledge_base_id\` to each copied hit metadata, merges results, then calls \`rank_by_similarity\`.
- A failure in one store is skipped; if all selected stores are empty or unavailable, return an empty list.
- Change \`ChatService.answer\` to accept \`knowledge_base_ids: str | Sequence[str]\` and optional \`knowledge_base_names: Mapping[str, str] | None = None\`; a string remains valid for old callers.
- Each citation includes \`knowledge_base_id\` and \`knowledge_base_name\` when available.

- [ ] **Step 1: Write the failing tests**

\`\`\`python
def test_retrieval_search_many_queries_only_selected_stores_and_merges_hits():
    result = service.search_many(["kb-b", "kb-a"], "问题", top_k=3)
    assert [hit.metadata["knowledge_base_id"] for hit in result] == ["kb-a", "kb-b"]
    assert embedder.calls == ["问题"]
    assert factory.requested_ids == ["kb-b", "kb-a"]


def test_retrieval_search_many_skips_one_failed_store():
    result = service.search_many(["kb-b", "kb-good"], "问题", top_k=5)
    assert [hit.metadata["knowledge_base_id"] for hit in result] == ["kb-good"]
\`\`\`

Add a ChatService test that calls \`answer([...], ..., knowledge_base_names={...})\` and asserts the emitted citation contains the selected knowledge base name and the prompt still contains the hit text.

- [ ] **Step 2: Run tests to verify they fail**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_retrieval.py tests/test_chat.py -k "many or selected_stores or knowledge_base_name" -v
\`\`\`

Expected: FAIL because only single-ID retrieval and single-ID ChatService input exist.

- [ ] **Step 3: Write minimal implementation**

Encode once per query, copy hit metadata instead of mutating shared store results, catch per-store exceptions, and use the existing stable \`rank_by_similarity\`. Preserve the calculator branch and its current event sequence.

- [ ] **Step 4: Run tests to verify they pass**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_retrieval.py tests/test_chat.py -v
\`\`\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add app/services/retrieval.py app/services/chat.py tests/test_retrieval.py tests/test_chat.py
git commit -m "feat: search across selected knowledge bases"
\`\`\`

### Task 3: 对话页知识库菜单与会话选择状态

**Files:**
- Modify: \`app/ui/chat_page.py: ChatPage header and selector methods\`
- Modify: \`app/ui/main_window.py: session lifecycle and query dispatch\`
- Test: \`tests/test_ui_smoke.py\`

**Interfaces:**
- Add \`ChatPage.knowledge_bases_changed = Signal(object)\` emitting the selected ID list.
- Add a top-right \`QPushButton\` with text \`⋯\`, object name \`ChatOptionsButton\`, and a \`QMenu\` containing checkable \`QAction\`s.
- Add \`ChatPage.set_knowledge_base_options(options: list[tuple[str, str]], selected_ids: list[str]) -> None\`.
- Add \`ChatPage.selected_knowledge_base_ids() -> list[str]\`.
- The menu includes a checkable “全选” action, keeps at least one knowledge base checked, and updates the button tooltip to \`已选择 N 个知识库\`.
- \`MainWindow\` maintains \`current_knowledge_base_ids: list[str]\`, while preserving \`current_knowledge_base_id\` as the first selected ID for existing knowledge-page behavior.
- \`new_session\`, \`load_session\`, \`select_knowledge_base\`, and \`receive_query\` synchronize this list with \`ChatSession\` and \`ChatPage\`.

- [ ] **Step 1: Write the failing tests**

\`\`\`python
def test_chat_page_knowledge_menu_supports_multi_select_and_select_all():
    page = ChatPage()
    page.set_knowledge_base_options(
        [("kb-a", "学习"), ("kb-b", "学生守则")],
        ["kb-a"],
    )
    page.knowledge_menu_actions["kb-b"].trigger()
    assert page.selected_knowledge_base_ids() == ["kb-a", "kb-b"]

    page.knowledge_menu_actions["__all__"].trigger()
    assert page.selected_knowledge_base_ids() == ["kb-a", "kb-b"]
\`\`\`

Add a MainWindow smoke test that creates two knowledge bases, starts a session, sets both IDs, saves/reloads it, and asserts the chat page restores both checks.

- [ ] **Step 2: Run tests to verify they fail**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_smoke.py -k "knowledge_menu or restores_both" -v
\`\`\`

Expected: FAIL because ChatPage has no options menu and ChatSession is still single-selection in MainWindow.

- [ ] **Step 3: Write minimal implementation**

Build the menu from current state data, connect \`knowledge_bases_changed\` to a MainWindow slot, persist the selection on the current session, and refresh options after creating, renaming, deleting, or loading a knowledge base. When a selected ID no longer exists, filter it and fall back to the current available knowledge base.

- [ ] **Step 4: Run tests to verify they pass**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_smoke.py -k "knowledge_menu or restores_both" -v
\`\`\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add app/ui/chat_page.py app/ui/main_window.py tests/test_ui_smoke.py
git commit -m "feat: add per-chat knowledge base selector"
\`\`\`

### Task 4: 来源行与右侧回答依据联动

**Files:**
- Modify: \`app/ui/chat_page.py: citation row widgets and display_messages\`
- Modify: \`app/ui/context_panels.py: CitationCard and CitationPanel\`
- Modify: \`app/ui/main_window.py: citation selection slot\`
- Test: \`tests/test_ui_smoke.py\`
- Test: \`tests/test_workspace.py\`

**Interfaces:**
- Add \`ChatPage.citation_requested = Signal(object)\` emitting the citation list for one assistant response.
- Add a clickable \`CitationLink\` widget with \`set_citations(citations: list[dict])\` and a click signal; it renders one concise source line, not a message bubble.
- Change \`ChatPage.append_citations(citations)\` to create this clickable source row and keep the existing streaming layout behavior.
- \`display_messages\` must append each stored assistant message’s citations immediately after that message, preserving response-to-citation ownership.
- \`CitationPanel.set_citations\` shows file name, knowledge base name, score, page where available, and preview; empty state remains unchanged.
- \`MainWindow._show_message_citations(citations)\` updates the panel and switches the context stack to it without changing the current conversation.

- [ ] **Step 1: Write the failing tests**

\`\`\`python
def test_chat_page_source_row_emits_only_its_response_citations():
    page = ChatPage()
    citations = [{"file_name": "a.md", "document_id": "doc-a"}]
    spy = QSignalSpy(page.citation_requested)
    page.append_citations(citations)

    source_row = page.messages.itemWidget(page.messages.item(0))
    source_row.click()

    assert spy.count() == 1
    assert spy.at(0)[0] == citations
\`\`\`

Add a test loading two assistant messages with different citations, clicking the first source row, and asserting the emitted payload is the first list. Add a CitationPanel assertion that a citation with \`knowledge_base_name\` renders that name.

- [ ] **Step 2: Run tests to verify they fail**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_smoke.py tests/test_workspace.py -k "source_row or response_citations or knowledge_base_name" -v
\`\`\`

Expected: FAIL because the current source line is a non-clickable QLabel without response ownership.

- [ ] **Step 3: Write minimal implementation**

Use a small transparent clickable widget or flat button with word wrapping. Store the citation list on the widget rather than using a global “latest citation” value. Keep the right panel’s existing no-horizontal-scroll behavior.

- [ ] **Step 4: Run tests to verify they pass**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_smoke.py tests/test_workspace.py -v
\`\`\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add app/ui/chat_page.py app/ui/context_panels.py app/ui/main_window.py tests/test_ui_smoke.py tests/test_workspace.py
git commit -m "feat: link chat sources to citation panel"
\`\`\`

### Task 5: 工具调用改为透明状态行并完成深色样式

**Files:**
- Modify: \`app/ui/chat_page.py: append_tool_call\`
- Modify: \`app/ui/theme.py: ToolCallLabel and source-link styles\`
- Test: \`tests/test_ui_smoke.py\`

**Interfaces:**
- Keep \`ChatPage.append_tool_call(tool_call: dict) -> None\` and object name \`ToolCallLabel\` for compatibility.
- The rendered widget must have transparent background, no border, no border radius, and a left accent indicator or equivalent text marker.
- Tool text remains selectable and wraps within the message viewport.

- [ ] **Step 1: Write the failing test**

\`\`\`python
def test_tool_call_is_a_transparent_status_row_not_a_bubble():
    page = ChatPage()
    page.append_tool_call({
        "name": "calculator",
        "result": {"success": True, "expression": "2+2", "result": "4"},
    })
    widget = page.messages.itemWidget(page.messages.item(0))

    assert widget.objectName() == "ToolCallLabel"
    assert "2+2" in widget.text()
    assert "border-radius" not in widget.styleSheet()
\`\`\`

- [ ] **Step 2: Run test to verify it fails**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_smoke.py -k "transparent_status_row" -v
\`\`\`

Expected: FAIL because the current global stylesheet gives \`ToolCallLabel\` a filled rounded background and border.

- [ ] **Step 3: Write minimal implementation**

Replace the filled tool label style with a transparent status-row style, use spacing and a left accent border only, and preserve the current height recalculation for multiline results.

- [ ] **Step 4: Run test to verify it passes**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_smoke.py -k "tool_call" -v
\`\`\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add app/ui/chat_page.py app/ui/theme.py tests/test_ui_smoke.py
git commit -m "style: render tool calls as status rows"
\`\`\`

### Task 5.5: 对话工作台视觉与轻量动效优化

**Files:**
- Modify: \`app/ui/chat_page.py: header, source rows, tool rows, entry animation helper\`
- Modify: \`app/ui/context_panels.py: citation panel hierarchy and selected state\`
- Modify: \`app/ui/theme.py: dark palette, menu, source row, tool row, spacing\`
- Test: \`tests/test_ui_smoke.py\`
- Test: \`tests/test_workspace.py\`

**Interfaces:**
- Keep the PySide6 implementation; do not add React, GSAP, npm, or browser runtime dependencies.
- Add a small Qt animation helper for newly inserted source/tool rows. It may animate only opacity and a small transform-like visual property, must keep animation objects alive until completion, and must not animate list width/height/top/left on every frame.
- Use one short timeline-like sequence for a new assistant response: assistant content appears first, then source row/tool status row; no animation should run for the entire message history on reload.
- The right citation panel keeps a stable width and no horizontal scrollbar; its active citation card receives a visible selected state.
- The three-dot button and menu must have a clear hover/pressed/focus state and remain keyboard reachable.

- [ ] **Step 1: Write the failing visual-contract tests**

\`\`\`python
def test_chat_page_uses_distinct_options_button_and_source_row_style():
    page = ChatPage()
    assert page.knowledge_options_button.objectName() == "ChatOptionsButton"
    page.append_citations([{"file_name": "学习笔记.md", "document_id": "doc-1"}])
    source_row = page.messages.itemWidget(page.messages.item(0))
    assert source_row.objectName() == "CitationLink"
    assert source_row.minimumHeight() >= 28


def test_citation_panel_marks_the_selected_card():
    panel = CitationPanel()
    panel.set_citations([{"file_name": "学习笔记.md", "document_id": "doc-1"}])
    panel.select_citation("doc-1")
    card = panel.source_list.itemWidget(panel.source_list.item(0))
    assert card.property("selected") is True
\`\`\`

Add a style assertion that \`ToolCallLabel\` contains no filled background or rounded border and that the source row uses the same dark palette accent as the rest of the chat workspace.

- [ ] **Step 2: Run the visual-contract tests to verify they fail**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest -p no:anyio tests/test_ui_smoke.py tests/test_workspace.py -k "distinct_options_button or selected_card or visual_contract" -v
\`\`\`

Expected: FAIL because the current page has no finalized selector object contract, no selected citation API, and no visual polish contract.

- [ ] **Step 3: Write the minimal visual implementation**

Use a restrained dark palette: one mint accent, one cool border tone, and transparent list backgrounds. Improve hierarchy with consistent 8/12/16px spacing, a compact options button, a menu section label, a source row with a small leading marker and hover underline, and a tool row with a thin accent rail. Use \`QPropertyAnimation\` only for a 140–180ms opacity entrance on the newly inserted row; retain references and stop/release them on completion. Do not add ScrollTrigger because the desktop application has no DOM scroll lifecycle; preserve native scrolling and call no animation from resize handlers.

- [ ] **Step 4: Run the visual-contract tests to verify they pass**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest -p no:anyio tests/test_ui_smoke.py tests/test_workspace.py -k "distinct_options_button or selected_card or visual_contract" -v
\`\`\`

Expected: PASS.

- [ ] **Step 5: Run the focused UI regression suite**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest -p no:anyio tests/test_ui_smoke.py tests/test_workspace.py -v
\`\`\`

Expected: PASS with the existing bubble, wrapping, right-rail width, source, tool, and menu tests preserved.

- [ ] **Step 6: Commit**

\`\`\`powershell
git add app/ui/chat_page.py app/ui/context_panels.py app/ui/theme.py tests/test_ui_smoke.py tests/test_workspace.py
git commit -m "style: polish chat workspace hierarchy and motion"
\`\`\`


### Task 6: 端到端回归与验收

**Files:**
- Modify: \`tests/test_chat.py\` only if an existing compatibility assertion needs the documented string-input adapter.
- Modify: \`tests/test_ui_smoke.py\` only if the new public UI behavior needs an additional regression case.
- Verify: all changed production and test files from Tasks 1–5.5.

**Interfaces:**
- No new production interfaces. This task validates the complete path from menu selection to retrieval to citation click.

- [ ] **Step 1: Add the end-to-end failing regression test**

Add this focused integration test to `tests/test_ui_smoke.py`, using a fake ChatService on the window so the test never loads a real model:

```python
def test_end_to_end_selected_knowledge_bases_reach_chat_service(monkeypatch, tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    first = state.create_knowledge_base("学习")
    second = state.create_knowledge_base("学生守则")
    window = MainWindow(config, state, first.id)
    window.new_session()

    received = {}

    class FakeService:
        def answer(self, query, knowledge_base_ids, model_id, history, knowledge_base_names=None):
            received["query"] = query
            received["knowledge_base_ids"] = list(knowledge_base_ids)
            yield ChatEvent("citation", [{
                "file_name": "学生守则.docx",
                "knowledge_base_name": "学生守则",
                "document_id": "doc-1",
            }])
            yield ChatEvent("token", "回答")
            yield ChatEvent("done", {})

    monkeypatch.setattr(window, "_chat_service", lambda: FakeService())
    window._set_current_knowledge_base_ids([first.id, second.id])
    window.receive_query("课程规则是什么？")
    application.processEvents()

    assert received["knowledge_base_ids"] == [first.id, second.id]
    window.close()
    application.processEvents()
```

- [ ] **Step 2: Run the regression test and verify it fails before the final wiring is complete**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_smoke.py -k "end_to_end_selected_knowledge" -v
\`\`\`

Expected before the MainWindow wiring is implemented: FAIL with an assertion or missing `_set_current_knowledge_base_ids`/multi-ID argument, proving the test covers the new path rather than existing single-ID behavior.

- [ ] **Step 3: Run focused tests**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest tests/test_models.py tests/test_storage.py tests/test_retrieval.py tests/test_chat.py tests/test_workspace.py tests/test_ui_smoke.py -v
\`\`\`

Expected: PASS with zero failures.

- [ ] **Step 4: Run the complete test suite**

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest -q
\`\`\`

Expected: all tests pass, with no collection errors.

- [ ] **Step 5: Run static and repository checks**

\`\`\`powershell
git diff --check
git status --short
\`\`\`

Expected: no whitespace errors; only intentional implementation changes remain.

- [ ] **Step 6: Commit the verified implementation**

\`\`\`powershell
git add app tests
git commit -m "feat: improve chat knowledge selection and evidence links"
\`\`\`
