from __future__ import annotations

import json
from pathlib import Path

from app.models import ModelDefinition


DEFAULT_MODELS = [
    ModelDefinition(
        id="qwen2.5-1.5b",
        display_name="Qwen2.5 1.5B",
        model_name="Qwen/Qwen2.5-1.5B-Instruct",
    )
]


class ModelRegistry:
    def __init__(self, state_path: Path):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._models = self._load()

    def list_models(self) -> list[ModelDefinition]:
        return list(self._models)

    def add_model(self, definition: ModelDefinition) -> None:
        self._models = [model for model in self._models if model.id != definition.id]
        self._models.append(definition)
        self._save()

    def get(self, model_id: str) -> ModelDefinition:
        for model in self._models:
            if model.id == model_id:
                return model
        raise KeyError(f"未注册的模型: {model_id}")

    def _load(self) -> list[ModelDefinition]:
        if not self.path.exists():
            self._save_models(DEFAULT_MODELS)
            return list(DEFAULT_MODELS)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return [ModelDefinition.from_dict(item) for item in raw]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            self._save_models(DEFAULT_MODELS)
            return list(DEFAULT_MODELS)

    def _save(self) -> None:
        self._save_models(self._models)

    def _save_models(self, models: list[ModelDefinition]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps([model.to_dict() for model in models], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

