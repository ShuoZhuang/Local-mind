# 工具中心筛选项精简实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 工具中心只显示“全部”“已启用”“本地能力”三个筛选项，并保持搜索、卡片布局和工具/能力分区正确工作。

**Architecture:** 筛选项列表和 `_refresh_visibility()` 位于 `ToolCenterPage`。保留按 `enabled` 与能力集合分区的行为，移除旧分类按钮及不可达的分类匹配分支；工具和能力的 `category` 元数据不变。测试通过公开的按钮字典与可见 ID 方法验证 UI 行为。

**Tech Stack:** Python 3.10、PySide6、pytest。

## Global Constraints

- 不修改 `data/` 内用户知识库数据。
- 不删除工具或本地能力的 `category` 元数据。
- 不覆盖当前工作区任何既有未提交 MCP/UI 改动。
- 测试使用 `G:\trial_project\004\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider` 的既有环境约定。

---

### Task 1: 精简工具中心筛选栏并更新行为测试

**Files:**
- Modify: `tests/test_tool_center.py`
- Modify: `app/ui/tool_center_page.py`

**Interfaces:**
- Consumes: `ToolCenterPage.category_buttons: dict[str, QPushButton]`、`visible_tool_ids() -> list[str]`、`visible_capability_ids() -> list[str]`。
- Produces: 筛选按钮键按插入顺序为 `[“全部”, “已启用”, “本地能力”]`；三种状态分别过滤全部卡片、已接入工具和本地能力。

- [ ] **Step 1: 写入失败测试**

在 `tests/test_tool_center.py` 增加以下测试，并将现有依赖 `category_buttons["检索"]` 的测试改为保留筛选项的等价断言：

```python
def test_tool_center_only_exposes_product_filter_buttons():
    page = ToolCenterPage()
    page.set_tools(definitions(), DEFAULT_LOCAL_CAPABILITIES)

    assert list(page.category_buttons) == ["全部", "已启用", "本地能力"]
    assert "计算" not in page.category_buttons
    assert "检索" not in page.category_buttons
    assert "文档" not in page.category_buttons

    page.category_buttons["已启用"].click()
    assert page.visible_tool_ids() == ["calculator"]
    assert page.visible_capability_ids() == []

    page.category_buttons["本地能力"].click()
    assert page.visible_tool_ids() == []
    assert page.visible_capability_ids() == [
        "document-parser", "chunking", "embedding", "knowledge-retrieval", "chroma-store",
    ]
    page.close()
```

- [ ] **Step 2: 运行目标测试并确认失败**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest tests/test_tool_center.py -q -p no:anyio -p no:cacheprovider
```

预期：新测试因当前按钮列表仍含“计算”“检索”“文档”而失败；旧测试若仍引用“检索”则在实现前保持现状。

- [ ] **Step 3: 写入最小实现**

在 `app/ui/tool_center_page.py` 中：

```python
for category in ("全部", "已启用", "本地能力"):
    # 保持已有 QPushButton 创建、checkable 设置与 clicked 连接
```

并将可调用工具的 `matches_category` 收敛为：

```python
matches_category = category == "全部" or (category == "已启用" and tool.enabled)
```

将本地能力的 `matches_category` 收敛为：

```python
matches_category = category in {"全部", "本地能力"}
```

这会使本地能力不受其“文档”或“检索”元数据影响，并确保不会因未来工具的同名分类而被错误纳入本地能力视图。

- [ ] **Step 4: 运行目标测试并确认通过**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest tests/test_tool_center.py -q -p no:anyio -p no:cacheprovider
```

预期：`tests/test_tool_center.py` 全部通过。

- [ ] **Step 5: 运行完整回归**

运行：

```powershell
.\.venv_gpu\Scripts\python.exe -u -m pytest -q -p no:anyio -p no:cacheprovider
```

预期：完整测试套件通过，且没有因已移除的筛选按钮产生 `KeyError`。

- [ ] **Step 6: 提交本任务文件**

```powershell
git add -- app/ui/tool_center_page.py tests/test_tool_center.py
git commit -m "feat: simplify tool center filters"
```
