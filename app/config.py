from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    root: Path
    data_dir: Path
    documents_dir: Path
    chroma_dir: Path
    models_dir: Path
    state_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> "AppConfig":
        root = Path(root).resolve()
        data_dir = root / "data"
        return cls(
            root=root,
            data_dir=data_dir,
            documents_dir=data_dir / "documents",
            chroma_dir=data_dir / "chroma_db",
            models_dir=data_dir / "models",
            state_dir=data_dir / "state",
        )

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.documents_dir,
            self.chroma_dir,
            self.models_dir,
            self.state_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

