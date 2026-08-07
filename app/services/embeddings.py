from __future__ import annotations

from pathlib import Path


class EmbeddingService:
    def __init__(self, model_name: str, cache_folder: Path, device: str = "auto"):
        self.model_name = model_name
        self.cache_folder = Path(cache_folder)
        self.device = self._choose_device(device)
        self._model = None

    @staticmethod
    def _choose_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self.cache_folder.mkdir(parents=True, exist_ok=True)
            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=str(self.cache_folder),
                device=self.device,
            )
        return self._model

    @staticmethod
    def _with_prefix(text: str, prefix: str) -> str:
        if text.startswith(prefix):
            return text
        return f"{prefix}{text}"

    def encode_query(self, text: str) -> list[float]:
        value = self._with_prefix(text.strip(), "query: ")
        return self._encode([value])[0]

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        values = [self._with_prefix(text.strip(), "passage: ") for text in texts]
        return self._encode(values)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if hasattr(self.model, "encode_document"):
            encoded = self.model.encode_document(texts, normalize_embeddings=True, convert_to_numpy=True)
        else:
            encoded = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return encoded.tolist()

