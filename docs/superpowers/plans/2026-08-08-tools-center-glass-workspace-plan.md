# Tools Center Glass Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有 PySide6 LocalMind 应用中实现已确认的深色玻璃工具中心三栏工作台。

**Architecture:** 新增 `ToolCenterPage` 负责搜索、筛选和工具卡片选择；新增 `ToolDetailsPanel` 负责右侧详情；`Sidebar` 增加工具入口但保留知识库和最近对话列表；`MainWindow` 负责页面切换和详情同步。工具元数据通过轻量展示注册表提供，不修改现有工具执行协议。

**Tech Stack:** Python 3.10、PySide6、现有 `APP_STYLE` QSS、pytest、Qt offscreen smoke tests。

## Global Constraints

- 不修改模型加载、知识库索引、对话协议或工具执行安全策略。
- 左侧保留“对话 / 知识库 / 工具”主导航，工具页下方保留“我的知识库”和“最近对话”。
- 不产生水平滚动条，长文本自动换行。
- 仅使用现有 PySide6 和标准库，不新增第三方依赖。

### Task 1: 工具中心数据模型和卡片页面

**Files:**
- Create: `app/ui/tool_center_page.py`
- Modify: `app/ui/theme.py`
- Test: `tests/test_tool_center.py`

**Interfaces:**
- `ToolDefinition`：展示用不可变数据，包含 `id`, `name`, `category`, `description`, `capabilities`, `enabled`, `icon_text`, `recent_calls`。
- `ToolCenterPage.tool_selected = Signal(str)`。
- `ToolCenterPage.set_tools(tools: list[ToolDefinition])`。
- `ToolCenterPage.selected_tool_id() -> str | None`。
- `ToolDetailsPanel.set_tool(tool: ToolDefinition | None)`。

- [ ] **Step 1: 编写失败测试**：验证默认工具列表、搜索过滤、分类过滤、卡片选择信号和详情更新。
- [ ] **Step 2: 运行测试确认失败**：`pytest tests/test_tool_center.py -q`，预期因新模块不存在而失败。
- [ ] **Step 3: 实现最小页面**：用 `QLineEdit`、筛选按钮、`QScrollArea` 和网格卡片构建中栏；卡片用 `QFrame#ToolCard`，选中状态用动态属性；右侧详情使用滚动区域和按钮。
- [ ] **Step 4: 更新主题**：补充工具卡片、筛选标签、状态点和详情面板的深色玻璃近似样式，确保 `QScrollBar:horizontal` 隐藏。
- [ ] **Step 5: 运行测试确认通过**：`pytest tests/test_tool_center.py -q`。

### Task 2: 侧栏与主窗口接入

**Files:**
- Modify: `app/ui/sidebar.py`
- Modify: `app/ui/main_window.py`
- Modify: `app/ui/workspace.py`
- Test: `tests/test_ui_smoke.py`
- Test: `tests/test_workspace.py`

**Interfaces:**
- `Sidebar.tool_page_requested = Signal()`。
- `MainWindow.show_tool_page()` 负责打开工具中心并同步详情。
- `WorkspaceShell.set_context_page()` 继续用于右侧详情切换。

- [ ] **Step 1: 为侧栏入口写测试**：验证工具按钮存在、点击后发出信号，且知识库列表和会话列表仍存在。
- [ ] **Step 2: 实现侧栏入口**：在“对话 / 知识库”之后添加“工具”，不移动或删除“我的知识库”和“最近对话”。
- [ ] **Step 3: 接入页面栈**：`MainWindow` 创建 `ToolCenterPage` 和 `ToolDetailsPanel`，增加到 stack/context stack，连接工具选择和侧栏信号。
- [ ] **Step 4: 保持右侧栏稳定**：工具中心使用现有 `WorkspaceShell`，右侧栏保持固定宽度、可折叠和可展开。
- [ ] **Step 5: 运行 UI smoke tests**：`pytest tests/test_ui_smoke.py tests/test_workspace.py -q`。

### Task 3: 真实工具元数据和回归验证

**Files:**
- Modify: `app/ui/main_window.py`
- Modify: `app/services/tool_router.py` only if metadata adapter needs a public helper
- Test: `tests/test_tool_center.py`
- Test: `tests/test_tool_router.py`

- [ ] **Step 1: 编写工具元数据测试**：验证计算器是启用状态，未接入的展示项不会伪装成可执行工具。
- [ ] **Step 2: 提供展示注册表**：至少包含高级计算器、语义检索、文档解析、知识库检索、文件检查、单位换算；只有实际已接入的能力标记为启用。
- [ ] **Step 3: 运行相关单元测试**：`pytest tests/test_tool_center.py tests/test_tool_router.py -q`。
- [ ] **Step 4: 运行完整测试**：`pytest -q`，记录已有失败而不掩盖；确认新增测试和 UI smoke 通过。
- [ ] **Step 5: 做一次 offscreen 启动检查**：构造 `MainWindow`，进入工具页，点击卡片，确认详情标题同步，随后关闭窗口。
- [ ] **Step 6: 提交实现**：`git add app tests docs/superpowers/plans/2026-08-08-tools-center-glass-workspace-plan.md && git commit -m "feat: add glass tools center workspace"`。
