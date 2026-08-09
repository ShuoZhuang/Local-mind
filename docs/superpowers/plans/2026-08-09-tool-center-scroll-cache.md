# Tool Center Scroll and MCP Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Tool Center reliably scroll, keep the test action reachable, preserve editable MCP display text, and load MCP tool cards from a local cache at startup.

**Architecture:** `LocalStateStore` owns two JSON files: an MCP discovery snapshot and per-tool display overrides. `ToolRegistry` hydrates the snapshot at construction and refreshes it only after MCP configuration changes. The Tool Center uses a dedicated scrolling card viewport, while the right detail panel separates scrolling information from a persistent action footer.

**Tech Stack:** Python 3.10, PySide6, pytest, local JSON state, stdio MCP client.

## Global Constraints

- Target project: `G:\\trial_project\\004`; do not modify the unrelated phase projects.
- Preserve the current MCP server configuration fields and existing model-call protocol.
- Opening the Tool Center must not start `npx`, an MCP server process, or discovery.
- A new MCP tool displays the server-provided title and description until the user saves a display override.
- User-facing copy is Chinese; raw MCP schemas remain available for testing and parameter validation.
- Keep the existing local-tool/local-capability distinction.

---

### Task 1: Persist MCP discovery snapshots and user display overrides

**Files:**
- Modify: `app/models.py:137-249`
- Modify: `app/services/storage.py:18-66`
- Modify: `app/services/tool_registry.py:12-125`
- Modify: `app/services/tool_contracts.py:8-119`
- Modify: `tests/test_tool_registry.py`

**Interfaces:**
- Produces `MCPToolDisplayMetadata(server_id, tool_name, display_name, description)` with `to_dict()` and `from_dict()`.
- Produces `LocalStateStore.load_mcp_tool_snapshot() -> list[dict[str, Any]]`, `save_mcp_tool_snapshot(entries: list[dict[str, Any]]) -> None`, `get_mcp_tool_display_metadata(server_id: str, tool_name: str) -> MCPToolDisplayMetadata | None`, and `save_mcp_tool_display_metadata(metadata: MCPToolDisplayMetadata) -> None`.
- Produces `ToolRegistry.refresh_mcp_tools() -> list[ToolDefinition]` that writes a snapshot, and `ToolRegistry` construction that hydrates enabled-server entries from the snapshot without calling `MCPClientService.discover`.

- [ ] **Step 1: Write the failing registry tests**

```python
def test_registry_hydrates_enabled_mcp_tools_from_snapshot_without_discovery(tmp_path):
    store = LocalStateStore(tmp_path)
    server = MCPServerDefinition.new("天气", "npx")
    store.save_mcp_server(server)
    store.save_mcp_tool_snapshot([{
        "server_id": server.id,
        "tool_name": "get_forecast",
        "title": "get_forecast",
        "description": "Get future weather forecast for a location.",
        "input_schema": {"type": "object"},
    }])
    client = FakeMCPClient()

    registry = ToolRegistry(store, client)

    tool = registry.get(f"mcp:{server.id}:get_forecast")
    assert client.discover_calls == []
    assert tool is not None
    assert tool.description == "Get future weather forecast for a location."


def test_registry_uses_saved_display_override_after_snapshot_hydration(tmp_path):
    store = LocalStateStore(tmp_path)
    server = MCPServerDefinition.new("天气", "npx")
    store.save_mcp_server(server)
    store.save_mcp_tool_snapshot([{
        "server_id": server.id,
        "tool_name": "get_forecast",
        "title": "get_forecast",
        "description": "Get future weather forecast for a location.",
        "input_schema": {"type": "object"},
    }])
    store.save_mcp_tool_display_metadata(
        MCPToolDisplayMetadata(server.id, "get_forecast", "天气预报", "查看指定城市未来天气。")
    )

    tool = ToolRegistry(store, FakeMCPClient()).get(f"mcp:{server.id}:get_forecast")

    assert tool.name == "天气预报"
    assert tool.description == "查看指定城市未来天气。"
```

- [ ] **Step 2: Run the tests to verify the interfaces are absent**

Run: `python -m pytest tests/test_tool_registry.py -k "snapshot or display_override" -v`

Expected: FAIL because the state methods and `MCPToolDisplayMetadata` do not exist.

- [ ] **Step 3: Add state models and JSON persistence**

```python
@dataclass(frozen=True)
class MCPToolDisplayMetadata:
    server_id: str
    tool_name: str
    display_name: str = ""
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPToolDisplayMetadata":
        return cls(
            server_id=str(data["server_id"]),
            tool_name=str(data["tool_name"]),
            display_name=str(data.get("display_name", "")).strip(),
            description=str(data.get("description", "")).strip(),
        )
```

Add `mcp_tool_snapshot.json` and `mcp_tool_display_metadata.json` paths in `LocalStateStore.__init__`. Read malformed snapshot values as an empty list. Upsert presentation metadata by `(server_id, tool_name)`.

- [ ] **Step 4: Add cache hydration and snapshot writes in `ToolRegistry`**

```python
def _hydrate_mcp_tools_from_snapshot(self) -> None:
    servers = {server.id: server for server in self.state.list_mcp_servers() if server.enabled}
    self._mcp_servers = servers
    for snapshot in self.state.load_mcp_tool_snapshot():
        server = servers.get(str(snapshot.get("server_id", "")))
        if server is not None:
            self._register_mcp_tool(server, snapshot)
```

Create `_register_mcp_tool(server, payload)` to build `ToolDefinition` from either an `MCPToolInfo` discovery result or a snapshot dict. Use `state.get_mcp_tool_display_metadata` to choose an override when non-empty; otherwise use `payload["title"]` / `payload["description"]`. Keep `input_schema` unmodified. On `refresh_mcp_tools`, rebuild in-memory tools, write enabled server entries to the snapshot, and preserve previous successful entries for a server whose discovery fails.

- [ ] **Step 5: Run registry and MCP tests**

Run: `python -m pytest tests/test_tool_registry.py tests/test_mcp_client.py tests/test_tool_contracts.py -v`

Expected: PASS. The hydration test proves no discovery occurs at construction, and refresh tests prove calls still route through the live server configuration.

- [ ] **Step 6: Commit the focused data-layer change**

```bash
git add app/models.py app/services/storage.py app/services/tool_registry.py app/services/tool_contracts.py tests/test_tool_registry.py
git commit -m "feat: cache MCP tools and display metadata"
```

### Task 2: Make tool details scroll and keep test actions reachable

**Files:**
- Modify: `app/ui/tool_center_page.py:140-470`
- Modify: `tests/test_tool_center.py`
- Modify: `tests/test_mcp_server_dialog.py`

**Interfaces:**
- Produces `ToolCenterPage.cards_scroll_area` as a vertically scrollable card viewport with horizontal scrolling disabled.
- Produces `ToolDetailsPanel.details_scroll_area` for labels, schema and results, while `test_button` remains outside that scroll area in a persistent footer.
- Produces `ToolDetailsPanel.edit_display_requested = Signal(str)` for selected MCP tools.

- [ ] **Step 1: Write failing Qt tests for scroll ownership and stable test action**

```python
def test_tool_center_card_viewport_is_vertical_scroll_only():
    app()
    page = ToolCenterPage()
    assert page.cards_scroll_area.verticalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.cards_scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_tool_details_keep_test_button_outside_scrollable_content():
    app()
    panel = ToolDetailsPanel()
    panel.set_tool(_mcp_tool_with_large_schema())
    assert panel.details_scroll_area.widget().findChild(type(panel.test_button)) is None
    assert panel.test_button.parentWidget() is not panel.details_scroll_area.widget()
```

- [ ] **Step 2: Run the scroll tests to verify the expected attributes are absent**

Run: `python -m pytest tests/test_tool_center.py tests/test_mcp_server_dialog.py -k "scroll or stable" -v`

Expected: FAIL because `cards_scroll_area` and `details_scroll_area` do not exist.

- [ ] **Step 3: Implement independent center and detail scroll containers**

```python
self.cards_scroll_area = QScrollArea()
self.cards_scroll_area.setWidgetResizable(True)
self.cards_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
self.cards_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
self.cards_scroll_area.setWidget(self.cards_container)
```

Replace the existing card scroll member with `cards_scroll_area`, set its viewport and content widget to expanding/minimum sizing so grid rows determine the scroll range, and remove the trailing stretch that can consume content height. In `ToolDetailsPanel`, build a scroll area containing title/status/description/schema/recent/result widgets; add the action row containing `编辑显示信息` and `测试调用` to the outer layout after the scroll area. Ensure horizontal scroll bars are always off and all long labels wrap.

- [ ] **Step 4: Expose the display-edit action only for MCP tools**

```python
self.edit_display_button.setVisible(tool is not None and tool.kind == "mcp")
self.edit_display_button.setEnabled(tool is not None and tool.kind == "mcp")
```

Emit the selected tool ID from `_emit_edit_display`. Keep local capabilities without either edit or test actions, and keep calculator testable but not display-editable.

- [ ] **Step 5: Run Tool Center and dialog tests**

Run: `python -m pytest tests/test_tool_center.py tests/test_mcp_server_dialog.py -v`

Expected: PASS. Existing filter tests, the test-action JSON test, and the new scroll ownership tests pass.

- [ ] **Step 6: Commit the interface change**

```bash
git add app/ui/tool_center_page.py tests/test_tool_center.py tests/test_mcp_server_dialog.py
git commit -m "fix: make tool center panels scroll independently"
```

### Task 3: Add the display-information editor and limit discovery to saved configuration changes

**Files:**
- Create: `app/ui/mcp_tool_display_dialog.py`
- Modify: `app/ui/main_window.py:48-258`
- Modify: `tests/test_mcp_server_dialog.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces `MCPToolDisplayDialog(state: LocalStateStore, tool: ToolDefinition, parent=None)` that writes `MCPToolDisplayMetadata`.
- `MainWindow._edit_mcp_tool_display(tool_id: str) -> None` opens the dialog and refreshes the Tool Center after saved metadata.
- `MainWindow.show_tool_page()` renders the cached registry only; it does not call `_discover_mcp_tools`.
- `MCPServerDialog.servers_changed` remains the configuration event that invokes `_discover_mcp_tools`.

- [ ] **Step 1: Write failing tests for editing and no startup discovery**

```python
def test_display_dialog_saves_optional_name_and_description(tmp_path):
    app()
    store = LocalStateStore(tmp_path)
    tool = ToolDefinition(id="mcp:server:get_forecast", name="get_forecast", category="MCP", description="raw", kind="mcp")
    dialog = MCPToolDisplayDialog(store, tool)
    dialog.display_name_input.setText("天气预报")
    dialog.description_input.setPlainText("查看未来几天的天气。")
    dialog.save_metadata()
    metadata = store.get_mcp_tool_display_metadata("server", "get_forecast")
    assert metadata.display_name == "天气预报"


def test_opening_tool_page_does_not_start_mcp_discovery(tmp_path, monkeypatch):
    window = _window_with_mcp_server(tmp_path)
    calls = []
    monkeypatch.setattr(window, "_discover_mcp_tools", lambda: calls.append("discover"))
    window.show_tool_page()
    assert calls == []
```

- [ ] **Step 2: Run the two tests to verify the dialog and lifecycle behavior are absent**

Run: `python -m pytest tests/test_mcp_server_dialog.py tests/test_ui_smoke.py -k "display_dialog or opening_tool_page" -v`

Expected: FAIL because `MCPToolDisplayDialog` and `_edit_mcp_tool_display` do not exist, or because `show_tool_page` schedules discovery.

- [ ] **Step 3: Implement the focused display editor dialog**

```python
class MCPToolDisplayDialog(QDialog):
    def save_metadata(self) -> None:
        _prefix, server_id, tool_name = self.tool.id.split(":", 2)
        self.state.save_mcp_tool_display_metadata(
            MCPToolDisplayMetadata(
                server_id=server_id,
                tool_name=tool_name,
                display_name=self.display_name_input.text().strip(),
                description=self.description_input.toPlainText().strip(),
            )
        )
        self.accept()
```

Show the raw MCP title and description as read-only hint text, and allow either editable field to remain blank so the UI falls back to the original Server text.

- [ ] **Step 4: Wire the dialog and remove opening-time discovery**

```python
def show_tool_page(self):
    self.sidebar.activate_tool_context()
    self.context_stack.setCurrentWidget(self.tool_details_panel)
    self.stack.setCurrentWidget(self.tool_center_page)
    self._refresh_registered_tools()
```

Delete `_mcp_discovery_started` and the `QTimer.singleShot(0, self._discover_mcp_tools)` branch. Connect `tool_details_panel.edit_display_requested` to `_edit_mcp_tool_display`. On accepted dialog, call a focused `reload_display_metadata()` method and refresh the Tool Center without performing discovery. Keep `MCPServerDialog.servers_changed.connect(self._discover_mcp_tools)` so saving/deleting a server remains the one place that triggers background discovery and snapshot replacement.

- [ ] **Step 5: Run targeted UI tests and the full suite**

Run: `python -m pytest tests/test_mcp_server_dialog.py tests/test_tool_center.py tests/test_ui_smoke.py tests/test_tool_registry.py -v`

Expected: PASS.

Run: `python -m pytest -q`

Expected: PASS with no regression in chat, RAG, tool calling, document ingestion, and UI smoke tests.

- [ ] **Step 6: Commit the dialog and lifecycle change**

```bash
git add app/ui/mcp_tool_display_dialog.py app/ui/main_window.py tests/test_mcp_server_dialog.py tests/test_ui_smoke.py
git commit -m "feat: edit MCP display text and defer discovery"
```

## Plan self-review

- Spec coverage: Task 1 covers persisted snapshots and editable per-tool metadata; Task 2 covers independent scrolling and a permanently reachable test action; Task 3 covers user editing and the no-discovery-at-open lifecycle.
- Placeholder scan: no unresolved placeholders or implicit test steps remain.
- Type consistency: `MCPToolDisplayMetadata`, `load_mcp_tool_snapshot`, `save_mcp_tool_snapshot`, and `MCPToolDisplayDialog` are defined before later tasks consume them.
