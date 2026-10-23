"""Model providers reachable through an OpenAI-compatible Chat Completions API.

Shared by weeks 2-4. (Week 1 keeps its own registry in week1_brochure.config,
which predates this module.)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

# The SDK retries 408/409/429/5xx with exponential backoff (0.5 s doubling, 8 s cap).
# Its default of 2 retries gives up after about a second, too short for a capacity spike.
DEFAULT_MAX_RETRIES = 5


@dataclass(frozen=True)
class Provider:
    name: str
    key_vars: tuple[str, ...]  # environment variables checked for the API key, in order
    base_url: str | None  # None means the OpenAI SDK's default (api.openai.com)
    local: bool = False  # a server on this machine that needs no real key

    def api_key(self, env: Mapping[str, str]) -> str | None:
        found = next((env[var] for var in self.key_vars if env.get(var)), None)
        if found is None and self.local:
            return "local"  # the SDK insists on some key; local servers ignore it
        return found

    def missing_key_message(self) -> str:
        return f"No API key for {self.name}: set {' or '.join(self.key_vars)} in .env."


PROVIDERS: dict[str, Provider] = {
    # Google's OpenAI-compatible endpoint. GOOGLE_API_KEY is the name the course uses.
    "gemini": Provider(
        "gemini",
        ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "openai": Provider("openai", ("OPENAI_API_KEY",), None),
    # Hugging Face Inference Providers router: open-weight models without a local GPU.
    "huggingface": Provider("huggingface", ("HF_TOKEN",), "https://router.huggingface.co/v1"),
    # Ollama's OpenAI-compatible server: open models on your own machine.
    "ollama": Provider("ollama", ("OLLAMA_API_KEY",), "http://localhost:11434/v1", local=True),
}


def get_provider(name: str) -> Provider:
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown provider {name!r}; choose one of: {', '.join(PROVIDERS)}"
        ) from None


def client_for(provider: Provider, api_key: str, **kwargs: Any) -> AsyncOpenAI:
    """An OpenAI SDK client pointed at the provider's endpoint."""
    kwargs.setdefault("max_retries", DEFAULT_MAX_RETRIES)
    return AsyncOpenAI(api_key=api_key, base_url=provider.base_url, **kwargs)
