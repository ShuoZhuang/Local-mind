# 知识库工作台重做 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将知识库页面重做为图 4 风格的工作台，并让文档只有在用户确认后才开始处理。

**Architecture:** `KnowledgePage` 只负责工作台展示、导入配置面板和用户确认信号；`MainWindow` 负责确认后的导入任务与状态更新；分段策略继续复用现有 `ChunkingConfig` 和策略实现。上传文件与开始处理分成两个明确动作。

**Tech Stack:** PySide6、现有本地 Embedding、Chroma、pytest。

## Global Constraints

- 不修改 `G:\trial_project\001`。
- 不接入云端服务或大模型 API。
- 中文界面，处理状态只在用户点击确认后出现。
- 自定义分隔符必须支持预设选项和用户手动输入。

### Task 1: 重建分隔符配置控件

**Files:**
- Modify: `app/ui/knowledge_page.py`
- Test: `tests/test_ui_smoke.py`

- [ ] 增加预设分隔符下拉框：换行、两个换行、中文句号、中文逗号、英文句号、英文逗号、中文问号、英文问号、自定义。
- [ ] 只有选择“自定义”时显示自定义输入框。
- [ ] `chunking_config()` 正确把预设映射成真实分隔符。
- [ ] 先写失败测试，再运行测试确认失败，再实现并验证通过。

### Task 2: 重建知识库工作台布局

**Files:**
- Modify: `app/ui/knowledge_page.py`
- Test: `tests/test_ui_smoke.py`

- [ ] 顶部显示知识库标题、文档数、片段数和“添加内容”按钮。
- [ ] 主区域使用左侧文档列表、右侧文档预览/详情布局。
- [ ] 首页不直接显示分段策略表单。
- [ ] 没有文档或没有选择文档时显示空状态。
- [ ] 保留文档搜索和状态显示。

### Task 3: 实现确认式导入面板

**Files:**
- Modify: `app/ui/knowledge_page.py`
- Modify: `app/ui/main_window.py`
- Test: `tests/test_ui_smoke.py`

- [ ] 点击“添加内容”打开导入面板。
- [ ] 选择文件后只显示文件信息，不发送处理信号。
- [ ] 点击“确认并开始处理”才发送 `file_import_requested`。
- [ ] 支持策略、分隔符、长度、重叠度和预处理设置。
- [ ] 导入面板显示预计片段数和少量预览占位。

### Task 4: 处理进度层与最终验收

**Files:**
- Modify: `app/ui/main_window.py`
- Modify: `tests/test_ui_smoke.py`

- [ ] 确认后显示处理进度层。
- [ ] 处理成功后关闭进度层并刷新文档列表。
- [ ] 处理失败后关闭进度层并保留失败原因。
- [ ] 运行完整测试：`\.venv_gpu\Scripts\python.exe -m pytest -q -p no:cacheprovider`。
