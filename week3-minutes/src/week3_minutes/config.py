"""Settings for the minutes generator. The default runs an open model on your own machine."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from labkit.providers import get_provider

DEFAULT_MODELS = {
    "ollama": "llama3.2",  # 3B, runs on a laptop
    "huggingface": "meta-llama/Llama-3.1-8B-Instruct",  # the course's model; gated on HF
    "gemini": "gemini-3.5-flash-lite",
    "openai": "gpt-4.1-mini",
}


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, provider: str | None = None
    ) -> Settings:
        env = os.environ if env is None else env
        name = get_provider(provider or env.get("MINUTES_PROVIDER") or "ollama").name
        return cls(provider=name, model=env.get("MINUTES_MODEL") or DEFAULT_MODELS[name])
