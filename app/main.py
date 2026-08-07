from __future__ import annotations

import sys
from pathlib import Path

from app.config import AppConfig
from app.services.storage import LocalStateStore


def build_window(project_root: Path | None = None):
    from app.ui.main_window import MainWindow

    root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
    config = AppConfig.from_root(root)
    config.ensure_directories()
    state = LocalStateStore(config.state_dir)
    return MainWindow(config, state)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    application = QApplication(sys.argv)
    window = build_window()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
