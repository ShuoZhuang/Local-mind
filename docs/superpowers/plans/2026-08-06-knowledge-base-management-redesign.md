# 知识库管理重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local knowledge-base dashboard with document records, three configurable chunking strategies, document details, chunk inspection, and safe reprocessing.

**Architecture:** Keep parsing, chunking, catalog persistence, vector operations, and Qt views separate. The ingestion service orchestrates `parse → strategy → embedding → Chroma → catalog`; the UI only emits typed requests and renders catalog records. Existing Chroma collections remain per knowledge base.

**Tech Stack:** Python 3.10, PySide6, ChromaDB, Sentence Transformers, PyMuPDF, python-docx, pytest.

## Global Constraints

- Project root is `G:\trial_project\004`; do not modify `001`.
- Keep all files, vectors, models, and state local; do not add APIs or cloud storage.
- Run UI tests with `QT_QPA_PLATFORM=offscreen`.
- Run tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `-p no:cacheprovider`.
- Use `G:\trial_project\004\.venv_gpu\Scripts\python.exe` for tests and application execution.
- Do not initialize Git: the project is not currently a Git repository.
- Persist one global last-used strategy configuration, but persist the actual configuration snapshot on each document.

---

### Task 1: Persist document records and global strategy defaults

**Files:**
- Modify: `app/models.py`
- Modify: `app/services/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces `DocumentRecord`, `ChunkingConfig`, and `ChunkingStrategyId` for ingestion and UI layers.
- Produces `LocalStateStore.list_documents(knowledge_base_id)`, `save_document(record)`, `get_document(document_id)`, `delete_document_record(document_id)`, `load_chunking_default()`, and `save_chunking_default(config)`.

- [ ] **Step 1: Write failing storage tests**

```python
def test_document_record_round_trips_and_is_scoped_to_knowledge_base(tmp_path):
    store = LocalStateStore(tmp_path)
    config = ChunkingConfig(strategy_id="custom", delimiter="\n", max_length=800)
    record = DocumentRecord.new("kb-a", "notes.md", "abc123", config)

    store.save_document(record)

    assert store.list_documents("kb-a") == [record]
    assert store.list_documents("kb-b") == []
    assert store.get_document(record.id).config.strategy_id == "custom"


def test_last_used_chunking_config_round_trips(tmp_path):
    store = LocalStateStore(tmp_path)
    config = ChunkingConfig(strategy_id="hierarchical", max_length=600, overlap_percent=15)

    store.save_chunking_default(config)

    assert store.load_chunking_default() == config
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_storage.py -q -p no:cacheprovider
```

Expected: import errors for `DocumentRecord` and `ChunkingConfig`, or missing `LocalStateStore` methods.

- [ ] **Step 3: Add typed models**

Add these definitions to `app/models.py`:

```python
ChunkingStrategyId = Literal["auto", "custom", "hierarchical"]


@dataclass(frozen=True)
class ChunkingConfig:
    strategy_id: ChunkingStrategyId = "auto"
    delimiter: str = "\n"
    max_length: int = 800
    overlap_percent: int = 10
    normalize_whitespace: bool = True
    remove_urls_emails: bool = False
    preserve_structure: bool = True


@dataclass
class DocumentRecord:
    id: str
    knowledge_base_id: str
    file_name: str
    file_hash: str
    source_path: str
    status: Literal["processing", "ready", "failed"]
    chunk_count: int
    config: ChunkingConfig
    error: str | None
    fallback_message: str | None
    created_at: str
    updated_at: str
```

Implement `new`, `to_dict`, and `from_dict`. Use this constructor signature:

```python
@classmethod
def new(
    cls,
    knowledge_base_id: str,
    file_name: str,
    file_hash: str,
    config: ChunkingConfig,
    source_path: str = "",
) -> "DocumentRecord":
```

It must generate an ID beginning with `doc-`, set status to `processing`, chunk count to `0`, and use `now_iso()` for both timestamps. Ingestion replaces the initially empty `source_path` with the copied local file path after a successful import.

- [ ] **Step 4: Add catalog persistence methods**

Use two JSON files under the existing state root:

```python
self.documents_path = self.root / "documents.json"
self.chunking_default_path = self.root / "chunking_default.json"
```

Implement document updates by replacing an item with the same `id`; list results must be sorted by `updated_at` descending. `load_chunking_default()` must return `ChunkingConfig()` if the file is absent or malformed.

- [ ] **Step 5: Run the storage tests and full existing storage suite**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_storage.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Checkpoint**

No Git commit is possible in this project. Record the passing test command and output in the implementation handoff.

### Task 2: Implement the three chunking strategies and parser sections

**Files:**
- Create: `app/services/chunking.py`
- Modify: `app/services/documents.py`
- Test: `tests/test_chunking.py`
- Test: `tests/test_documents.py`

**Interfaces:**
- Consumes `ChunkingConfig` from Task 1.
- Produces `ExtractedSection(page: int | None, text: str, heading_path: tuple[str, ...] = ())` and `ChunkingResult(pieces: list[ChunkPiece], fallback_message: str | None)`.
- Produces `build_chunker(config: ChunkingConfig) -> ChunkingStrategy`.

- [ ] **Step 1: Write failing strategy tests**

```python
def test_custom_chunker_uses_named_preset_and_custom_delimiter():
    config = ChunkingConfig(strategy_id="custom", delimiter="###", max_length=800)
    result = build_chunker(config).split([ExtractedSection(None, "A###B")])
    assert [piece.text for piece in result.pieces] == ["A", "B"]


def test_hierarchical_markdown_preserves_heading_path():
    sections = extract_sections_from_text("# 第一章\n正文\n## 1.1 概念\n细节", suffix=".md")
    result = build_chunker(ChunkingConfig(strategy_id="hierarchical")).split(sections)
    assert result.pieces[-1].heading_path == ("第一章", "1.1 概念")


def test_hierarchical_chunker_falls_back_when_no_heading_exists():
    result = build_chunker(ChunkingConfig(strategy_id="hierarchical")).split(
        [ExtractedSection(None, "只有普通文本。")]
    )
    assert result.fallback_message == "未识别到明确层级，已使用自动分段。"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_chunking.py -q -p no:cacheprovider
```

Expected: module and symbol import failures.

- [ ] **Step 3: Create `app/services/chunking.py`**

Define these public types:

```python
@dataclass(frozen=True)
class ExtractedSection:
    page: int | None
    text: str
    heading_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkPiece:
    text: str
    page: int | None
    heading_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkingResult:
    pieces: list[ChunkPiece]
    fallback_message: str | None = None


class ChunkingStrategy(Protocol):
    def split(self, sections: list[ExtractedSection]) -> ChunkingResult:
        raise NotImplementedError
```

Implement `AutoChunker`, `CustomChunker`, and `HierarchicalChunker`. Reuse the current fixed-window splitting behavior for oversized text. All strategies must apply URL/email removal and whitespace normalization from `ChunkingConfig` before returning a `ChunkPiece`.

- [ ] **Step 4: Add source-aware extraction**

Replace the flattened extraction entry point with:

```python
def extract_sections(path: Path) -> list[ExtractedSection]:
```

Rules:

- TXT: one section, no heading path.
- Markdown: parse `^(#{1,6})\s+(.+)$`, maintain a stack of heading text, and create sections whose heading path reflects the active stack.
- DOCX: inspect each paragraph's `style.name`; recognize names beginning with `Heading` and Chinese `标题`; create sections with the active heading stack.
- PDF: emit one section per page, detect a first-line heading only when it matches `第.+章`, `\d+(\.\d+)+`, or `[一二三四五六七八九十]+、`; otherwise use no heading path.

Keep a compatibility wrapper `extract_text(path)` that returns `[(section.page, section.text) for section in extract_sections(path)]` until callers are migrated.

- [ ] **Step 5: Integrate `ingest_file` with chunkers**

Change its signature to:

```python
def ingest_file(path: Path, knowledge_base_id: str, config: ChunkingConfig) -> tuple[list[DocumentChunk], str | None, str]:
```

Return chunks, any fallback message, and the SHA-256 file hash. Put `heading_path` (joined with ` > `), `document_id` (added by the caller), `page`, and `chunk_index` into each chunk metadata map.

- [ ] **Step 6: Run strategy and existing document tests**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_chunking.py tests/test_documents.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Checkpoint**

No Git commit is possible in this project. Record the passing test command and output in the implementation handoff.

### Task 3: Make ingestion and Chroma document-aware and reprocessable

**Files:**
- Modify: `app/services/ingestion.py`
- Modify: `app/services/vector_store.py`
- Test: `tests/test_ingestion.py`
- Test: `tests/test_vector_store.py`

**Interfaces:**
- Consumes `DocumentRecord`, `ChunkingConfig`, and `ingest_file` from Tasks 1–2.
- Produces `KnowledgeBaseService.import_file(path, record, progress_callback)` and `reprocess_file(record, progress_callback)`.
- Produces vector-store methods `delete_document(document_id)`, `get_document_chunks(document_id)`, and `list_document_hashes()`.

- [ ] **Step 1: Write failing ingestion lifecycle tests**

```python
def test_reprocess_deletes_old_vectors_before_upserting_new_ones(tmp_path):
    calls = []
    store = FakeStore(calls)
    record = DocumentRecord.new("kb-ai", "note.md", "hash", ChunkingConfig())
    service = KnowledgeBaseService(FakeEmbedder(), lambda _: store)

    service.reprocess_file(tmp_path / "note.md", record)

    assert calls[0] == ("delete_document", record.id)
    assert calls[-1][0] == "upsert"


def test_import_records_fallback_message_and_chunk_count(tmp_path):
    record = DocumentRecord.new("kb-ai", "plain.txt", "hash", ChunkingConfig(strategy_id="hierarchical"))
    result = service.import_file(tmp_path / "plain.txt", record)
    assert result.record.status == "ready"
    assert result.record.chunk_count > 0
    assert result.record.fallback_message is not None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_ingestion.py tests/test_vector_store.py -q -p no:cacheprovider
```

Expected: missing reprocess API and vector-store methods.

- [ ] **Step 3: Extend the vector store**

Use document record IDs, not file hashes, as the deletion key:

```python
def delete_document(self, document_id: str) -> None:
    found = self.collection.get(where={"document_id": document_id})
    if found.get("ids"):
        self.collection.delete(ids=found["ids"])

def get_document_chunks(self, document_id: str) -> list[DocumentChunk]:
    found = self.collection.get(where={"document_id": document_id}, include=["documents", "metadatas"])
    ids = found.get("ids", [])
    texts = found.get("documents", [])
    metadatas = found.get("metadatas", [])
    return [
        DocumentChunk(identifier, text, metadata or {})
        for identifier, text, metadata in zip(ids, texts, metadatas)
    ]
```

Sort `get_document_chunks` by `metadata["chunk_index"]` before returning.

- [ ] **Step 4: Refactor ingestion around a document record**

Define:

```python
@dataclass(frozen=True)
class IngestionResult:
    record: DocumentRecord
    chunks: list[DocumentChunk]

def import_file(
    self,
    path: Path,
    record: DocumentRecord,
    progress_callback: Callable[[tuple[str, int]], None] | None = None,
) -> IngestionResult:
    return self._ingest(path, record, replace_existing=False, progress_callback=progress_callback)

def reprocess_file(
    self,
    path: Path,
    record: DocumentRecord,
    progress_callback: Callable[[tuple[str, int]], None] | None = None,
) -> IngestionResult:
    return self._ingest(path, record, replace_existing=True, progress_callback=progress_callback)
```

For both operations:

1. set/report `extracting`;
2. call `ingest_file` with `record.config`;
3. add `document_id=record.id` to every chunk metadata map;
4. report `embedding` and encode chunk texts;
5. for reprocessing, call `store.delete_document(record.id)` before `upsert`;
6. report `saving`, upsert chunks, copy the original file, set status `ready`, chunk count, fallback message, and `updated_at`;
7. on exception, set status `failed`, save the exception text in `error`, then re-raise so the worker reports it.

- [ ] **Step 5: Run ingestion/vector tests**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_ingestion.py tests/test_vector_store.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Checkpoint**

No Git commit is possible in this project. Record the passing test command and output in the implementation handoff.

### Task 4: Build the dashboard, strategy picker, and document detail drawer

**Files:**
- Create: `app/ui/segment_strategy.py`
- Create: `app/ui/document_detail.py`
- Modify: `app/ui/knowledge_page.py`
- Modify: `app/ui/theme.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes `DocumentRecord` and `ChunkingConfig` from Task 1.
- Produces `SegmentStrategyWidget.config() -> ChunkingConfig` and `KnowledgePage` signals for import, document selection, reprocess, delete, and chunk viewing.

- [ ] **Step 1: Write failing UI tests**

```python
def test_strategy_widget_shows_custom_fields_only_for_custom_choice(qapp):
    widget = SegmentStrategyWidget()
    widget.set_strategy("custom")
    assert widget.custom_panel.isVisible()
    assert widget.delimiter_combo.currentText() == "换行"
    widget.set_strategy("auto")
    assert not widget.custom_panel.isVisible()


def test_knowledge_page_switches_drawer_between_import_and_document_detail(qapp):
    page = KnowledgePage()
    page.show_import_drawer()
    assert page.drawer.currentWidget() is page.import_panel
    page.show_document_detail(DocumentRecord.new("kb", "a.md", "h", ChunkingConfig()))
    assert page.drawer.currentWidget() is page.detail_panel
```

- [ ] **Step 2: Run the new UI tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_ui_smoke.py -q -p no:cacheprovider
```

Expected: missing widgets and page methods.

- [ ] **Step 3: Create the strategy widget**

`SegmentStrategyWidget` must show three selectable cards: `自动分段与清洗`, `自定义`, and `按层级分段`. Its custom panel must contain:

```python
PRESET_DELIMITERS = {
    "换行": "\n", "2个换行": "\n\n", "中文句号": "。", "中文逗号": "，",
    "英文句号": ".", "英文逗号": ",", "中文问号": "？", "英文问号": "?",
}
```

Add a `自定义` combo option that reveals a `QLineEdit`; use `QSpinBox` labels `分段最大长度（字符）` and `分段重叠度（%）`; include three checkboxes matching the confirmed design. Add a preview label populated from a pure helper `estimate_chunks(text, config)`.

- [ ] **Step 4: Create the detail drawer**

`DocumentDetailWidget` must expose:

```python
view_chunks_requested = Signal(str)
reprocess_requested = Signal(str)
delete_requested = Signal(str)
def set_document(self, record: DocumentRecord) -> None:
    self.current_record = record
    self.file_name_label.setText(record.file_name)
    self.status_label.setText(record.status)
    self.chunk_count_label.setText(f"{record.chunk_count} 个片段")
```

Render file details, status, chunk count, strategy name, config summary, fallback message, and three action buttons. Disable `重新处理` and `删除` while the record status is `processing`.

- [ ] **Step 5: Replace the old one-column knowledge page**

Use a `QSplitter` with a dashboard on the left and a `QStackedWidget` drawer on the right. The dashboard must have summary cards, a search field, a status filter combo, an `＋ 添加文档` button, and a document list. Define signals:

```python
file_import_requested = Signal(Path, object)
document_selected = Signal(str)
reprocess_requested = Signal(str, object)
delete_document_requested = Signal(str)
view_chunks_requested = Signal(str)
```

`set_documents(records)` must render status text `已索引`, `处理中`, or `失败` and attach the document ID in `Qt.UserRole`.

- [ ] **Step 6: Run UI tests**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_ui_smoke.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Checkpoint**

No Git commit is possible in this project. Record the passing test command and output in the implementation handoff.

### Task 5: Wire catalog, workers, reprocess confirmation, and chunk viewer into the main window

**Files:**
- Create: `app/ui/chunk_viewer.py`
- Modify: `app/ui/main_window.py`
- Modify: `app/ui/workers.py`
- Test: `tests/test_ui_smoke.py`
- Test: `tests/test_ingestion.py`

**Interfaces:**
- Consumes signals from Task 4 and ingestion APIs from Task 3.
- Produces a working import/reprocess/delete lifecycle and `ChunkViewerDialog(document_id, chunks)`.

- [ ] **Step 1: Write failing integration tests**

```python
def build_window_with_document(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = AppConfig.from_root(tmp_path)
    state = LocalStateStore(config.state_dir)
    knowledge_base = state.create_knowledge_base("测试知识库")
    record = DocumentRecord.new(
        knowledge_base.id, "测试.md", "a" * 64, ChunkingConfig(strategy_id="auto")
    )
    record.status = "ready"
    record.chunk_count = 2
    state.save_document(record)
    window = MainWindow(config, state, knowledge_base.id)
    window.open_knowledge_base(knowledge_base.id)
    return window, record

def test_selecting_document_loads_detail_drawer(tmp_path, qapp):
    window, record = build_window_with_document(tmp_path)
    window.knowledge_page.document_selected.emit(record.id)
    assert window.knowledge_page.detail_panel.current_record.id == record.id


def test_reprocess_confirmation_mentions_old_vectors(tmp_path, monkeypatch, qapp):
    window, record = build_window_with_document(tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window.request_reprocess(record.id, ChunkingConfig(strategy_id="auto"))
    assert "旧片段和旧向量" in window.last_confirmation_text
```

- [ ] **Step 2: Run the new integration tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_ui_smoke.py tests/test_ingestion.py -q -p no:cacheprovider
```

Expected: missing document selection and reprocess APIs.

- [ ] **Step 3: Add a generic operation worker**

Add `CatalogOperationWorker(QObject)` to `app/ui/workers.py`:

```python
progress = Signal(object)
finished = Signal(object)
failed = Signal(str)

def __init__(self, operation: Callable[[Callable[[object], None]], object]):
    super().__init__()
    self.operation = operation

def run(self):
    try:
        self.finished.emit(self.operation(self.progress.emit))
    except Exception as exc:
        self.failed.emit(str(exc))
```

Keep `ImportWorker` temporarily as an alias or migrate its call sites in the same task. Both success and failure paths must quit their `QThread` in `MainWindow`.

- [ ] **Step 4: Load and update records in `MainWindow`**

Add these methods:

```python
def refresh_documents(self) -> None:
    self.knowledge_page.set_documents(self.state.list_documents(self.current_knowledge_base_id))

def open_document_detail(self, document_id: str) -> None:
    self.knowledge_page.show_document_detail(self.state.get_document(document_id))

def request_reprocess(self, document_id: str, config: ChunkingConfig) -> None:
    record = self.state.get_document(document_id)
    record.config = config
    self._confirm_and_start_reprocess(record)

def delete_document(self, document_id: str) -> None:
    record = self.state.get_document(document_id)
    self._delete_document_data(record)
    self.state.delete_document_record(document_id)
    self.refresh_documents()

def show_chunk_viewer(self, document_id: str) -> None:
    chunks = self._store_factory(self.current_knowledge_base_id).get_document_chunks(document_id)
    ChunkViewerDialog(document_id, chunks, self).exec()
```

On import, create and save a processing `DocumentRecord` before starting the worker. On worker success, save the ready record and refresh the dashboard. On failure, save the failed record, refresh the dashboard, and open its detail drawer.

For reprocessing, show this exact confirmation text before starting work:

```text
重新处理会删除该文档现有的旧片段和旧向量，并按新的分段策略重新建立索引。是否继续？
```

For deletion, delete vectors by `document_id`, delete the catalog record, then remove only the copied original file associated with that record. Do not recursively delete the knowledge-base directory.

- [ ] **Step 5: Implement the chunk viewer**

`ChunkViewerDialog` must use a searchable `QListWidget` or `QTableWidget`; each row displays `片段 {chunk_index}` plus page and heading path. Selecting a row displays full text in a read-only `QPlainTextEdit`.

- [ ] **Step 6: Run integration tests**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_ui_smoke.py tests/test_ingestion.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Checkpoint**

No Git commit is possible in this project. Record the passing test command and output in the implementation handoff.

### Task 6: Migrate existing local documents and complete verification

**Files:**
- Create: `app/services/document_migration.py`
- Modify: `app/ui/main_window.py`
- Modify: `README.md`
- Test: `tests/test_migration.py`

**Interfaces:**
- Consumes `LocalStateStore`, `KnowledgeBaseVectorStore`, and document records from Tasks 1–3.
- Produces `migrate_legacy_documents(state, config, store_factory) -> int`.

- [ ] **Step 1: Write the failing migration test**

```python
def test_migration_creates_legacy_record_for_existing_copied_file(tmp_path):
    config = AppConfig.from_root(tmp_path)
    kb = LocalStateStore(config.state_dir).create_knowledge_base("旧资料")
    copied = config.documents_dir / kb.id / "aabb_notes.md"
    copied.parent.mkdir(parents=True)
    copied.write_text("旧文档", encoding="utf-8")

    created = migrate_legacy_documents(state, config, fake_store_factory)

    assert created == 1
    assert state.list_documents(kb.id)[0].config.strategy_id == "auto"
```

- [ ] **Step 2: Run the migration test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.\.venv_gpu\Scripts\python.exe' -m pytest tests/test_migration.py -q -p no:cacheprovider
```

Expected: missing migration module.

- [ ] **Step 3: Implement conservative migration**

For each original file under `data/documents/<knowledge_base_id>/` without a catalog record, create a ready `DocumentRecord` using `ChunkingConfig(strategy_id="auto")`, source path set to the copied file, and chunk count from Chroma metadata when a matching file hash is available; otherwise use `0`. Never re-embed or re-chunk during migration.

- [ ] **Step 4: Call migration once at application startup**

Call it after `config.ensure_directories()` and before the first dashboard refresh. Migration must be idempotent: a second call returns `0` and creates no duplicate records.

- [ ] **Step 5: Update the README**

Document the three strategies, the local catalog files (`data/state/documents.json`, `data/state/chunking_default.json`), “查看全部片段”, and the reprocess behavior.

- [ ] **Step 6: Run the complete test suite and GPU smoke check**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
& '.\.venv_gpu\Scripts\python.exe' -m pytest -q -p no:cacheprovider
& '.\.venv_gpu\Scripts\python.exe' -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Expected: all tests pass; CUDA is `True`; device name is `NVIDIA GeForce RTX 5070 Ti Laptop GPU`.

- [ ] **Step 7: Manual acceptance checklist**

1. Start `./run.ps1`.
2. Open a knowledge base and confirm existing documents appear once.
3. Import a Markdown file with headings using hierarchical mode; inspect title paths.
4. Import a plain text file using custom delimiter `###`; inspect the generated pieces.
5. Reprocess one document and confirm the warning text appears and chunk count updates.
6. Open “查看全部片段” and verify page, heading path, and full text are shown.
7. Delete only the test document and verify other documents remain intact.

- [ ] **Step 8: Checkpoint**

No Git commit is possible in this project. Report full test and manual acceptance results in the final handoff.
