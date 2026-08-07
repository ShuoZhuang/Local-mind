from PySide6.QtTest import QSignalSpy

from app.ui.workers import ImportWorker


def test_import_worker_emits_its_job_id_with_progress_and_result():
    worker = ImportWorker(lambda progress: (progress(("done", 100)), "result")[1], "doc-123")
    progress_spy = QSignalSpy(worker.progress)
    finished_spy = QSignalSpy(worker.finished)

    worker.run()

    assert progress_spy.at(0)[0] == "doc-123"
    assert progress_spy.at(0)[1] == ("done", 100)
    assert finished_spy.at(0)[0] == "doc-123"
    assert finished_spy.at(0)[1] == "result"
