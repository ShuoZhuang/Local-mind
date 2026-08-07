from __future__ import annotations

from pathlib import Path
import os
import stat
import shutil
import hashlib

from PySide6.QtCore import QThread, Qt, QTimer
from PySide6.QtWidgets import QDialog, QInputDialog, QListWidget, QMainWindow, QMessageBox, QProgressDialog, QSplitter, QStackedWidget, QWidget, QHBoxLayout, QVBoxLayout

from app.config import AppConfig
from app.models import ChatMessage, ChatSession, ChunkingConfig, DocumentRecord
from app.services.chat import ChatService, ChatEvent
from app.services.documents import SplitOptions
from app.services.embeddings import EmbeddingService
from app.services.ingestion import KnowledgeBaseService
from app.services.llm import LocalLLM
from app.services.model_registry import ModelRegistry
from app.services.retrieval import RetrievalService
from app.services.storage import LocalStateStore
from app.services.vector_store import KnowledgeBaseVectorStore
from app.ui.chat_page import ChatPage
from app.ui.context_panels import CitationPanel, DocumentDetailPanel, ImportProgressPanel, KnowledgeImportPanel, KnowledgeOverviewPanel
from app.ui.knowledge_page import KnowledgePage
from app.ui.sidebar import Sidebar
from app.ui.theme import APP_STYLE
from app.ui.workspace import WorkspaceShell
from app.ui.workers import ImportWorker, StreamWorker, WarmupWorker


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, state: LocalStateStore, initial_knowledge_base_id: str | None = None):
        super().__init__()
        self.config = config
        self.state = state
        self.config.ensure_directories()
        self.state.recover_stale_processing_documents()
        if not self.state.list_knowledge_bases():
            self.state.create_knowledge_base("我的第一个知识库", "上传文档开始建立本地知识库")
        self.model_registry = ModelRegistry(self.config.state_dir / "models.json")
        self.current_knowledge_base_id = initial_knowledge_base_id or self.state.list_knowledge_bases()[0].id
        self.current_knowledge_base_ids = [self.current_knowledge_base_id]
        self.current_model_id = self.model_registry.list_models()[0].id
        self.current_session: ChatSession | None = None
        self.current_messages: list[ChatMessage] = []
        self._assistant_text = ""
        self._pending_citations: list[dict] = []
        self._pending_tool_calls: list[dict] = []
        self._embedding_service = None
        self._llms = {}
        self._threads = []
        self._workers = []
        self._active_stream_worker = None
        self._preheat_in_progress = False
        self._import_jobs = {}
        self.import_progress: QProgressDialog | None = None
        self._build()

    def _build(self):
        self.setWindowTitle("LocalMind · 本地知识助手")
        self.resize(1180, 760)
        self.setStyleSheet(APP_STYLE)
        self.sidebar = Sidebar(self.state, self.model_registry)
        self.chat_page = ChatPage()
        self.knowledge_page = KnowledgePage()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.chat_page)
        self.stack.addWidget(self.knowledge_page)
        self.context_stack = QStackedWidget()
        self.knowledge_overview_panel = KnowledgeOverviewPanel()
        self.knowledge_import_panel = KnowledgeImportPanel()
        self.import_progress_panel = ImportProgressPanel()
        self.document_detail_panel = DocumentDetailPanel()
        self.citation_panel = CitationPanel()
        self.context_stack.addWidget(self.knowledge_overview_panel)
        self.context_stack.addWidget(self.knowledge_import_panel)
        self.context_stack.addWidget(self.import_progress_panel)
        self.context_stack.addWidget(self.document_detail_panel)
        self.context_stack.addWidget(self.citation_panel)
        self.workspace = WorkspaceShell(self.sidebar, self.stack, self.context_stack)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.workspace)
        self.setCentralWidget(container)
        self.sidebar.knowledge_base_selected.connect(self.open_knowledge_base)
        self.sidebar.model_selected.connect(self.select_model)
        self.sidebar.preheat_changed.connect(self._set_preheat_models)
        self.sidebar.new_session_requested.connect(self.new_session)
        self.sidebar.new_knowledge_base_requested.connect(self.new_knowledge_base)
        self.sidebar.session_selected.connect(self.load_session)
        self.sidebar.rename_knowledge_base_requested.connect(self.rename_knowledge_base)
        self.sidebar.delete_knowledge_base_requested.connect(self.delete_knowledge_base)
        self.sidebar.rename_session_requested.connect(self.rename_session)
        self.sidebar.delete_session_requested.connect(self.delete_session)
        self.sidebar.knowledge_page_requested.connect(self.show_knowledge_page)
        self.sidebar.chat_page_requested.connect(self.show_chat_page)
        self.chat_page.send_requested.connect(self.receive_query)
        self.chat_page.stop_requested.connect(self.stop_generation)
        self.chat_page.knowledge_bases_changed.connect(self._set_chat_knowledge_bases)
        self.chat_page.citations_requested.connect(self._show_selected_citations)
        self.knowledge_page.file_import_requested.connect(self.import_file)
        self.knowledge_page.file_selected.connect(self._show_import_settings)
        self.knowledge_page.document_selected.connect(self.open_document_detail)
        self.knowledge_page.document_reprocess_requested.connect(self.reprocess_document)
        self.knowledge_page.document_delete_requested.connect(self.delete_document)
        self.knowledge_page.view_chunks_requested.connect(self.view_document_chunks)
        self.document_detail_panel.reprocess_requested.connect(self.reprocess_document)
        self.document_detail_panel.delete_requested.connect(self.delete_document)
        self.citation_panel.document_requested.connect(self._open_citation_document)
        self.knowledge_import_panel.confirmed.connect(self._confirm_import_settings)
        self.knowledge_import_panel.cancelled.connect(self._cancel_import_settings)
        self.select_knowledge_base(self.current_knowledge_base_id)
        self.sidebar.activate_chat_context()
        self.context_stack.setCurrentWidget(self.citation_panel)
        self.citation_panel.set_empty_state("还没有回答依据。选择知识库并开始提问后，资料会显示在这里。")
        if self.state.load_preheat_models():
            QTimer.singleShot(0, self._preheat_models)

    def select_knowledge_base(self, knowledge_base_id: str):
        self.current_knowledge_base_id = knowledge_base_id
        self.current_knowledge_base_ids = [knowledge_base_id]
        item = next((item for item in self.state.list_knowledge_bases() if item.id == knowledge_base_id), None)
        if item:
            self.chat_page.set_knowledge_base(item.name)
            self.knowledge_page.set_knowledge_base(item.name)
            self.knowledge_page.set_documents(self.state.list_documents(knowledge_base_id))
            self.knowledge_page.set_chunking_config(self.state.load_chunking_default())
            self.knowledge_overview_panel.set_knowledge_base(name=item.name, document_count=len(self.state.list_documents(knowledge_base_id)))
        self._refresh_chat_knowledge_bases()

    def open_knowledge_base(self, knowledge_base_id: str):
        self.select_knowledge_base(knowledge_base_id)
        self.sidebar.activate_knowledge_context(knowledge_base_id)
        self.stack.setCurrentWidget(self.knowledge_page)

    def show_knowledge_page(self):
        self.sidebar.activate_knowledge_context(self.current_knowledge_base_id)
        self.context_stack.setCurrentWidget(self.knowledge_overview_panel)
        self.stack.setCurrentWidget(self.knowledge_page)

    def show_chat_page(self):
        session_id = self.current_session.id if self.current_session else None
        self.sidebar.activate_chat_context(session_id)
        self.context_stack.setCurrentWidget(self.citation_panel)
        self.stack.setCurrentWidget(self.chat_page)

    def select_model(self, model_id: str):
        self.current_model_id = model_id

    def _set_preheat_models(self, enabled: bool):
        self.state.save_preheat_models(enabled)
        if enabled:
            self._preheat_models()

    def _preheat_models(self):
        if self._preheat_in_progress:
            return
        self._preheat_in_progress = True
        self.sidebar.preheat_checkbox.setText("正在预热模型…")
        worker = WarmupWorker(self._warmup_models)
        thread = QThread(self)
        worker.moveToThread(thread)
        self._retain_worker(worker)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(self._on_preheat_finished)
        worker.failed.connect(self._on_preheat_failed)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._release_worker(worker))
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        thread.start()

    def _warmup_models(self):
        embedding = self._embedding()
        _ = embedding.model
        self._llm_factory(self.current_model_id).load()

    def _on_preheat_finished(self):
        self._preheat_in_progress = False
        self.sidebar.preheat_checkbox.setText("模型已预热")

    def _on_preheat_failed(self, message: str):
        self._preheat_in_progress = False
        self.sidebar.preheat_checkbox.setText("启动时预热模型")
        self.chat_page.subtitle.setText(f"模型预热失败：{message}")

    def new_session(self):
        self.current_session = ChatSession.new(self.current_knowledge_base_id, self.current_model_id)
        self.current_messages = []
        self._assistant_text = ""
        self._pending_citations = []
        self._pending_tool_calls = []
        self.chat_page.messages.clear()
        self._refresh_chat_knowledge_bases()
        self.chat_page.set_session_title(self.current_session.title)
        self.state.save_session(self.current_session, [])
        self.sidebar.refresh()
        self.sidebar.activate_chat_context(self.current_session.id)
        self.stack.setCurrentWidget(self.chat_page)

    def load_session(self, session_id: str):
        try:
            session, messages = self.state.load_session(session_id)
        except FileNotFoundError as exc:
            self._show_error(str(exc))
            return
        self.current_session = session
        self.current_messages = messages
        self.current_knowledge_base_id = session.knowledge_base_id
        self.current_knowledge_base_ids = session.selected_knowledge_base_ids()
        self.current_model_id = session.model_id
        self.select_knowledge_base(session.knowledge_base_id)
        self.current_knowledge_base_ids = session.selected_knowledge_base_ids()
        self._refresh_chat_knowledge_bases()
        self.chat_page.set_session_title(session.title)
        self.chat_page.display_messages(messages)
        self.sidebar.activate_chat_context(session.id)
        self.stack.setCurrentWidget(self.chat_page)

    def receive_query(self, text: str):
        if self.current_session is None:
            self.new_session()
        self.chat_page.set_generation_active(True)
        self.chat_page.append_user(text)
        self.chat_page.start_assistant()
        self.current_messages.append(ChatMessage("user", text))
        self._assistant_text = ""
        self._pending_citations = []
        self._pending_tool_calls = []
        service = self._chat_service()
        iterator = service.answer(
            text,
            self.current_knowledge_base_ids,
            self.current_model_id,
            self.current_messages[:-1],
            knowledge_base_names=self._knowledge_base_names(),
        )
        worker = StreamWorker(iterator)
        self._active_stream_worker = worker
        self._start_worker(worker, self._handle_chat_event)

    def stop_generation(self):
        if self._active_stream_worker is not None:
            self._active_stream_worker.cancel()
        self.chat_page.set_generation_active(False)

    def import_file(self, path: Path, config: ChunkingConfig | SplitOptions | None = None):
        if not isinstance(config, ChunkingConfig):
            config = self.state.load_chunking_default()
        self.state.save_chunking_default(config)
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        record = DocumentRecord.new(
            self.current_knowledge_base_id,
            path.name,
            file_hash,
            config,
            source_path=str(path),
        )
        self.state.save_document(record)
        status_id = self.knowledge_page.add_document_status(f"处理中：{path.name}", record.id)
        service = KnowledgeBaseService(
            self._embedding(),
            self._store_factory,
            self.config.documents_dir,
        )
        worker = ImportWorker(
            lambda progress: service.reprocess_file(path, record, progress),
            record.id,
        )
        self._start_import_worker(worker, path.name, status_id)

    def _show_import_settings(self, path: Path | list[Path]):
        paths = [Path(item) for item in path] if isinstance(path, (list, tuple)) else [Path(path)]
        self.knowledge_import_panel.set_pending_paths(paths)
        self.knowledge_import_panel.set_chunking_config(self.state.load_chunking_default())
        self.context_stack.setCurrentWidget(self.knowledge_import_panel)

    def _confirm_import_settings(self, path: Path | list[Path], config: ChunkingConfig):
        paths = path if isinstance(path, (list, tuple)) else [path]
        for item in paths:
            self.import_file(Path(item), config)
        self.context_stack.setCurrentWidget(self.knowledge_overview_panel)

    def _cancel_import_settings(self):
        self.context_stack.setCurrentWidget(self.knowledge_overview_panel)

    def open_document_detail(self, document_id: str):
        try:
            record = self.state.get_document(document_id)
        except KeyError:
            return
        self.knowledge_page.summary.setText(
            f"{record.file_name} · {record.status} · {record.chunk_count} 个片段 · "
            f"策略：{record.config.strategy_id}"
        )
        try:
            chunks = self._store_factory(record.knowledge_base_id).get_document_chunks(record.id)
            preview = "\n\n".join(chunk.text for chunk in chunks[:5])
        except Exception:
            chunks = []
            preview = ""
        self.knowledge_page.preview_text.setPlainText(preview)
        self.document_detail_panel.set_document(record, chunks)
        self.context_stack.setCurrentWidget(self.document_detail_panel)

    def _open_citation_document(self, document_id: str):
        self.open_knowledge_base(self.current_knowledge_base_id)
        self.open_document_detail(document_id)

    def _show_selected_citations(self, citations: list[dict]) -> None:
        self._pending_citations = list(citations)
        self.citation_panel.set_citations(self._pending_citations)
        self.context_stack.setCurrentWidget(self.citation_panel)

    def _set_chat_knowledge_bases(self, knowledge_base_ids: list[str]) -> None:
        if not knowledge_base_ids:
            return
        available = {item.id for item in self.state.list_knowledge_bases()}
        selected = [item for item in knowledge_base_ids if item in available]
        if not selected:
            return
        self.current_knowledge_base_ids = selected
        self.current_knowledge_base_id = selected[0]
        if self.current_session:
            self.current_session.set_knowledge_base_ids(selected)
            self.state.save_session(self.current_session, self.current_messages)
        names = self._knowledge_base_names()
        self.chat_page.subtitle.setText("回答将参考：" + "、".join(names[item] for item in selected if item in names))

    def _knowledge_base_names(self) -> dict[str, str]:
        return {item.id: item.name for item in self.state.list_knowledge_bases()}

    def _refresh_chat_knowledge_bases(self) -> None:
        options = [(item.id, item.name) for item in self.state.list_knowledge_bases()]
        self.chat_page.set_knowledge_bases(options, self.current_knowledge_base_ids)

    def reprocess_document(self, document_id: str):
        try:
            record = self.state.get_document(document_id)
        except KeyError:
            return
        source = Path(record.source_path)
        if not source.exists():
            self._show_error("找不到原始文档，无法重新处理。请重新上传该文件。")
            return
        answer = QMessageBox.question(
            self,
            "重新处理文档",
            "重新处理会删除该文档现有的全部片段和向量，再按当前分段策略重新建立索引。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        record.config = self.knowledge_page.chunking_config()
        record.status = "processing"
        record.error = None
        self.state.save_chunking_default(record.config)
        self.state.save_document(record)
        self.knowledge_page.set_documents(self.state.list_documents(record.knowledge_base_id))
        self.open_document_detail(record.id)
        service = KnowledgeBaseService(self._embedding(), self._store_factory, self.config.documents_dir)
        worker = ImportWorker(lambda progress: service.reprocess_file(source, record, progress), record.id)
        self._start_import_worker(worker, record.file_name, record.id)

    def delete_document(self, document_id: str):
        try:
            record = self.state.get_document(document_id)
        except KeyError:
            return
        answer = QMessageBox.question(
            self,
            "删除文档",
            f"确定删除“{record.file_name}”及其全部片段和向量吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._store_factory(record.knowledge_base_id).delete_document(record.id)
        source = Path(record.source_path)
        try:
            if source.is_file() and self.config.documents_dir.resolve() in source.resolve().parents:
                self._remove_readonly_file(source)
        except OSError:
            pass
        self.state.delete_document_record(document_id)
        self.knowledge_page.set_documents(self.state.list_documents(record.knowledge_base_id))

    def view_document_chunks(self, document_id: str):
        try:
            record = self.state.get_document(document_id)
        except KeyError:
            return
        chunks = self._store_factory(record.knowledge_base_id).get_document_chunks(document_id)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{record.file_name} · 全部片段")
        dialog.resize(760, 560)
        list_widget = QListWidget(dialog)
        for index, chunk in enumerate(chunks, start=1):
            list_widget.addItem(f"片段 {index}\n{chunk.text}")
        if not chunks:
            list_widget.addItem("当前文档还没有可查看的片段。")
        layout = QVBoxLayout(dialog)
        layout.addWidget(list_widget)
        dialog.exec()

    def new_knowledge_base(self):
        name, accepted = QInputDialog.getText(self, "新建知识库", "知识库名称：")
        if accepted and name.strip():
            knowledge_base = self.state.create_knowledge_base(name.strip())
            self.sidebar.refresh()
            self.open_knowledge_base(knowledge_base.id)

    def rename_knowledge_base(self, knowledge_base_id: str):
        item = next((item for item in self.state.list_knowledge_bases() if item.id == knowledge_base_id), None)
        if item is None:
            return
        name, accepted = QInputDialog.getText(self, "重命名知识库", "知识库名称：", text=item.name)
        if accepted:
            try:
                self.state.rename_knowledge_base(knowledge_base_id, name)
            except ValueError as exc:
                self._show_error(str(exc))
                return
            self.sidebar.refresh()
            self.open_knowledge_base(knowledge_base_id)

    def delete_knowledge_base(self, knowledge_base_id: str):
        item = next((item for item in self.state.list_knowledge_bases() if item.id == knowledge_base_id), None)
        if item is None:
            return
        answer = QMessageBox.question(
            self,
            "删除知识库",
            f"确定删除“{item.name}”及其本地文档和向量数据吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        cleanup_errors = self._delete_knowledge_base_data(knowledge_base_id)
        if self.current_session and knowledge_base_id in self.current_session.selected_knowledge_base_ids():
            self.current_session = None
            self.current_messages = []
            self.chat_page.messages.clear()
            self.chat_page.set_session_title("新对话")
        self.state.delete_documents_for_knowledge_base(knowledge_base_id)
        self.state.delete_sessions_for_knowledge_base(knowledge_base_id)
        self.state.delete_knowledge_base(knowledge_base_id)
        if not self.state.list_knowledge_bases():
            self.state.create_knowledge_base("新知识库", "上传文档开始建立本地知识库")
        next_id = self.state.list_knowledge_bases()[0].id
        self.sidebar.refresh()
        self.open_knowledge_base(next_id)
        if cleanup_errors:
            self.statusBar().showMessage(
                f"知识库“{item.name}”已删除，但有 {len(cleanup_errors)} 个本地文件未能清理",
                6000,
            )
        else:
            self.statusBar().showMessage(f"知识库“{item.name}”已删除", 4000)

    def rename_session(self, session_id: str):
        try:
            session, _ = self.state.load_session(session_id)
        except FileNotFoundError:
            return
        title, accepted = QInputDialog.getText(self, "重命名对话", "对话标题：", text=session.title)
        if accepted:
            self.state.update_session_title(session_id, title)
            if self.current_session and self.current_session.id == session_id:
                self.chat_page.set_session_title(title)
            self.sidebar.refresh()
            self.sidebar.activate_chat_context(session_id)

    def delete_session(self, session_id: str):
        answer = QMessageBox.question(
            self,
            "删除对话",
            "确定删除这条对话记录吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.state.delete_session(session_id)
        if self.current_session and self.current_session.id == session_id:
            self.current_session = None
            self.current_messages = []
            self.chat_page.messages.clear()
            self.chat_page.set_session_title("新对话")
        self.sidebar.refresh()

    @staticmethod
    def _remove_readonly_file(path: Path) -> None:
        try:
            path.unlink()
        except PermissionError:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            path.unlink()

    @staticmethod
    def _remove_readonly_on_error(function, path, _exc_info) -> None:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        function(path)

    def _delete_knowledge_base_data(self, knowledge_base_id: str) -> list[str]:
        cleanup_errors: list[str] = []
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.config.chroma_dir))
            client.delete_collection(f"kb_{knowledge_base_id}")
        except Exception:
            pass
        document_path = self.config.documents_dir / knowledge_base_id
        if document_path.exists():
            try:
                shutil.rmtree(document_path, onerror=self._remove_readonly_on_error)
            except OSError as exc:
                cleanup_errors.append(str(exc))
        return cleanup_errors

    def _embedding(self):
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService(
                "intfloat/multilingual-e5-small",
                self.config.models_dir / "embeddings",
            )
        return self._embedding_service

    def _store_factory(self, knowledge_base_id: str):
        return KnowledgeBaseVectorStore(self.config.chroma_dir, knowledge_base_id)

    def _retrieval(self):
        return RetrievalService(self._embedding(), self._store_factory)

    def _llm_factory(self, model_id: str):
        if model_id not in self._llms:
            self._llms[model_id] = LocalLLM(
                self.model_registry.get(model_id),
                self.config.models_dir / "llm",
            )
        return self._llms[model_id]

    def _chat_service(self):
        return ChatService(self._retrieval(), self._llm_factory)

    def _start_worker(self, worker: StreamWorker, handler):
        thread = QThread(self)
        worker.moveToThread(thread)
        self._retain_worker(worker)
        worker.event.connect(handler)
        worker.failed.connect(self._show_error)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.failed.connect(lambda _message: thread.quit())
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        thread.finished.connect(lambda: self._release_worker(worker))
        thread.start()

    def _start_import_worker(self, worker: ImportWorker, file_name: str, status_id: str):
        self._show_import_progress(file_name)
        thread = QThread(self)
        worker.moveToThread(thread)
        self._retain_worker(worker)
        self._import_jobs[status_id] = (file_name, status_id)
        worker.progress.connect(self._on_import_worker_progress)
        worker.finished.connect(self._on_import_worker_finished)
        worker.failed.connect(self._on_import_worker_failed)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.failed.connect(lambda _message: thread.quit())
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        thread.finished.connect(lambda: self._release_import_worker(worker))
        thread.start()

    def _retain_worker(self, worker):
        self._workers.append(worker)

    def _release_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def _release_import_worker(self, worker):
        self._import_jobs.pop(worker.job_id, None)
        self._release_worker(worker)

    def _on_import_worker_progress(self, job_id: str, value):
        job = self._import_jobs.get(job_id)
        if job:
            self._handle_import_progress(*job, value)

    def _on_import_worker_finished(self, job_id: str, result):
        job = self._import_jobs.get(job_id)
        if job:
            self._handle_import_finished(*job, result)

    def _on_import_worker_failed(self, job_id: str, message: str):
        job = self._import_jobs.get(job_id)
        if job:
            self._handle_import_failed(*job, message)

    def _handle_chat_event(self, event: ChatEvent):
        if event.kind == "status":
            self.chat_page.subtitle.setText(str(event.payload))
        elif event.kind == "citation":
            self._pending_citations = list(event.payload or [])
            self.citation_panel.set_citations(self._pending_citations)
            self.context_stack.setCurrentWidget(self.citation_panel)
        elif event.kind == "tool":
            tool_call = event.payload if isinstance(event.payload, dict) else {}
            self._pending_tool_calls.append(tool_call)
            result = tool_call.get("result", {})
            self.chat_page.subtitle.setText(
                "已使用计算工具" if result.get("success") else "计算工具返回了错误"
            )
        elif event.kind == "token":
            self._assistant_text += str(event.payload)
            self.chat_page.append_token(str(event.payload))
        elif event.kind == "done":
            self.chat_page.set_generation_active(False)
            self._active_stream_worker = None
            self.chat_page.append_citations(self._pending_citations)
            for tool_call in self._pending_tool_calls:
                self.chat_page.append_tool_call(tool_call)
            self.current_messages.append(
                ChatMessage(
                    "assistant",
                    self._assistant_text,
                    self._pending_citations,
                    self._pending_tool_calls,
                )
            )
            if self.current_session:
                if self.current_session.title == "新对话" and self.current_messages:
                    self.state.update_session_title(self.current_session.id, self.current_messages[0].content[:16])
                    self.current_session.title = self.current_messages[0].content[:16]
                    self.chat_page.set_session_title(self.current_session.title)
                    self.sidebar.refresh()
                self.current_session.updated_at = self.current_session.updated_at
                self.state.save_session(self.current_session, self.current_messages)

    def _handle_import_progress(self, file_name: str, status_id: str, value):
        stage, percent = value
        stage_labels = {
            "extracting": "正在解析和分段",
            "embedding": "正在生成向量（首次可能需要几十秒）",
            "embedding_done": "向量生成完成",
            "deleting_old": "正在清理旧索引",
            "saving": "正在写入 Chroma",
            "saved": "向量写入完成",
            "done": "处理完成",
        }
        stage_text = stage_labels.get(stage, stage)
        self.import_progress_panel.set_stage(stage_text, percent, file_name)
        if self.import_progress is not None:
            self.import_progress.setLabelText(f"正在处理：{file_name}\n{stage_text}")
            self.import_progress.setValue(percent)
        self.knowledge_page.summary.setText(f"{file_name} · {stage_text} · {percent}%")
        self.knowledge_page.update_document_status(status_id, f"处理中：{file_name} · {stage_text} · {percent}%")

    def _handle_import_finished(self, file_name: str, status_id: str, result):
        self._close_import_progress()
        self.state.save_document(result.record)
        self.knowledge_page.update_document_status(
            status_id,
            f"已索引：{file_name} · {len(result.chunks)} 个片段",
            state="success",
        )
        self.knowledge_page.set_documents(self.state.list_documents(self.current_knowledge_base_id))
        self.open_document_detail(status_id)
        self.sidebar.refresh()

    def _handle_import_failed(self, file_name: str, status_id: str, message: str):
        self._close_import_progress()
        try:
            record = self.state.get_document(status_id)
            record.status = "failed"
            record.error = message
            self.state.save_document(record)
        except KeyError:
            pass
        self.knowledge_page.update_document_status(
            status_id,
            f"失败：{file_name} · {message}",
            state="error",
        )
        self.knowledge_page.set_documents(self.state.list_documents(self.current_knowledge_base_id))
        self.open_document_detail(status_id)
        self._show_error(message)

    def _show_import_progress(self, file_name: str):
        self.import_progress_panel.set_stage("准备处理", 0, file_name)
        self.context_stack.setCurrentWidget(self.import_progress_panel)
        self._close_import_progress()
        progress = QProgressDialog(f"正在处理：{file_name}", None, 0, 100, self)
        progress.setWindowTitle("正在建立知识库")
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        self.import_progress = progress

    def _close_import_progress(self):
        if self.import_progress is not None:
            self.import_progress.close()
            self.import_progress.deleteLater()
            self.import_progress = None

    def _show_error(self, message: str):
        self.chat_page.set_generation_active(False)
        self.chat_page.append_error(message)
        self.knowledge_page.summary.setText(f"错误：{message}")
        self.chat_page.subtitle.setText(f"错误：{message}")
