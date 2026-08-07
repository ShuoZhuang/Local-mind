from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class StreamWorker(QObject):
    event = Signal(object)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, iterator):
        super().__init__()
        self.iterator = iterator
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            for event in self.iterator:
                if self.cancelled:
                    break
                self.event.emit(event)
            self.finished.emit()
        except Exception as exc:  # pragma: no cover - UI boundary
            self.failed.emit(str(exc))


class ImportWorker(QObject):
    progress = Signal(str, object)
    finished = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, operation, job_id: str = ""):
        super().__init__()
        self.operation = operation
        self.job_id = job_id

    def run(self):
        try:
            result = self.operation(lambda value: self.progress.emit(self.job_id, value))
            self.finished.emit(self.job_id, result)
        except Exception as exc:  # pragma: no cover - UI boundary
            self.failed.emit(self.job_id, str(exc))


class WarmupWorker(QObject):
    finished = Signal()
    failed = Signal(str)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    def run(self):
        try:
            self.operation()
            self.finished.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
