from __future__ import annotations

import os
from pathlib import Path
from threading import Thread
from typing import Callable, Iterator

from app.models import ModelDefinition


class LocalLLM:
    def __init__(self, model: ModelDefinition, cache_dir: Path):
        self.definition = model
        self.cache_dir = Path(cache_dir)
        self._tokenizer = None
        self._model = None
        try:
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            self.device = "cpu"

    def is_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def load(self, progress_callback: Callable[[str], None] | None = None) -> None:
        if self.is_loaded():
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("本地对话模型需要安装 torch 和 transformers") from exc

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        source = self.definition.local_path or self.definition.model_name
        offline = os.environ.get("LOCAL_AGENT_OFFLINE") == "1"
        if progress_callback:
            progress_callback(f"正在加载 {self.definition.display_name}（{self.device.upper()}）")
        self._tokenizer = AutoTokenizer.from_pretrained(
            source,
            cache_dir=str(self.cache_dir),
            local_files_only=offline,
        )
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self._model = AutoModelForCausalLM.from_pretrained(
            source,
            cache_dir=str(self.cache_dir),
            dtype=dtype,
            local_files_only=offline,
            device_map={"": self.device},
        )
        self._model.eval()
        if progress_callback:
            progress_callback("模型已加载")

    def generate_stream(self, messages: list[dict], max_new_tokens: int = 512) -> Iterator[str]:
        self.load()
        from transformers import TextIteratorStreamer

        prompt = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)
        streamer = TextIteratorStreamer(self._tokenizer, skip_prompt=True, skip_special_tokens=True)
        kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_new_tokens,
            "do_sample": True,
            "temperature": 0.7,
            "top_p": 0.9,
        }
        thread = Thread(target=self._model.generate, kwargs=kwargs, daemon=True)
        thread.start()
        yield from streamer
        thread.join(timeout=2)
