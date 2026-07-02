from __future__ import annotations

from pathlib import Path

from benchmarks.rair_rag.downstream.llm_clients import (
    LOCAL_QWEN_STOP_TOKENS,
    LocalLlamaCppGenerator,
)


class FakeLlama:
    def __init__(
        self,
        *,
        chat_response: dict | None = None,
        completion_response: dict | None = None,
        chat_error: Exception | None = None,
    ) -> None:
        self.chat_response = chat_response or {
            "choices": [{"message": {"content": '{"reply":"chat"}'}}]
        }
        self.completion_response = completion_response or {
            "choices": [{"text": '{"reply":"completion"}'}]
        }
        self.chat_error = chat_error
        self.chat_calls: list[dict] = []
        self.completion_calls: list[dict] = []

    def create_chat_completion(self, **kwargs):
        self.chat_calls.append(kwargs)
        if self.chat_error:
            raise self.chat_error
        return self.chat_response

    def __call__(self, prompt: str, **kwargs):
        self.completion_calls.append({"prompt": prompt, **kwargs})
        return self.completion_response


def test_local_llama_uses_chat_completion_first(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("", encoding="utf-8")
    fake = FakeLlama()
    generator = LocalLlamaCppGenerator(model_path=model)
    generator._llm = fake

    output = generator.generate("say json")

    assert output == '{"reply":"chat"}'
    assert generator.last_chat_mode == "chat_completion"
    assert fake.chat_calls
    assert fake.chat_calls[0]["messages"][0]["role"] == "system"
    assert fake.chat_calls[0]["messages"][1] == {
        "role": "user",
        "content": "say json",
    }
    assert fake.chat_calls[0]["stop"] == LOCAL_QWEN_STOP_TOKENS
    assert not fake.completion_calls


def test_local_llama_falls_back_to_qwen_manual_template(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("", encoding="utf-8")
    fake = FakeLlama(chat_error=RuntimeError("chat unsupported"))
    generator = LocalLlamaCppGenerator(model_path=model)
    generator._llm = fake

    output = generator.generate("say json")

    assert output == '{"reply":"completion"}'
    assert generator.last_chat_mode == "qwen_manual"
    assert fake.chat_calls
    assert fake.completion_calls
    prompt = fake.completion_calls[0]["prompt"]
    assert "<|im_start|>system" in prompt
    assert "<|im_start|>user\nsay json" in prompt
    assert prompt.endswith("<|im_start|>assistant\n")
    assert fake.completion_calls[0]["stop"] == LOCAL_QWEN_STOP_TOKENS


def test_local_llama_records_empty_generation_reason(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("", encoding="utf-8")
    fake = FakeLlama(completion_response={"choices": [{"text": ""}]})
    generator = LocalLlamaCppGenerator(model_path=model, chat_mode="qwen_manual")
    generator._llm = fake

    output = generator.generate("say json")

    assert output == ""
    assert generator.last_chat_mode == "qwen_manual"
    assert generator.last_reason == "empty_generation_after_chat_template"


def test_local_llama_completion_mode_uses_raw_prompt(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("", encoding="utf-8")
    fake = FakeLlama()
    generator = LocalLlamaCppGenerator(model_path=model, chat_mode="completion")
    generator._llm = fake

    output = generator.generate("raw prompt")

    assert output == '{"reply":"completion"}'
    assert generator.last_chat_mode == "completion"
    assert not fake.chat_calls
    assert fake.completion_calls[0]["prompt"] == "raw prompt"
