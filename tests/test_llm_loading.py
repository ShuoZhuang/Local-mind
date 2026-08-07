from app.models import ModelDefinition
from app.services.llm import LocalLLM


def test_load_uses_device_map_instead_of_moving_meta_model(monkeypatch, tmp_path):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    calls = {}

    class FakeTokenizer:
        pass

    class FakeModel:
        def eval(self):
            return self

        def to(self, *_args, **_kwargs):
            raise AssertionError("a model loaded with device_map must not be moved again")

    fake_model = FakeModel()

    def fake_tokenizer_loader(*_args, **kwargs):
        calls["tokenizer"] = kwargs
        return FakeTokenizer()

    def fake_model_loader(*_args, **kwargs):
        calls["model"] = kwargs
        return fake_model

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", fake_tokenizer_loader)
    monkeypatch.setattr(AutoModelForCausalLM, "from_pretrained", fake_model_loader)

    llm = LocalLLM(
        ModelDefinition(
            id="test-model",
            display_name="Test model",
            model_name="test/model",
        ),
        tmp_path,
    )
    llm.load()

    assert calls["model"]["device_map"] == {"": "cuda"}
    assert calls["model"]["dtype"] is torch.float16
    assert llm._model is fake_model
