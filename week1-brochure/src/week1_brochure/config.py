"""All tunable values in one place, so a run is reproducible from its settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """A model provider reachable through an OpenAI-compatible Chat Completions API."""

    name: str
    key_vars: tuple[str, ...]  # environment variables checked for the API key, in order
    base_url: str | None  # None means the OpenAI SDK's default (api.openai.com)
    link_model: str  # small, cheap model for picking pages
    writer_model: str  # stronger model for writing the brochure

    def api_key(self, env: Mapping[str, str]) -> str | None:
        return next((env[var] for var in self.key_vars if env.get(var)), None)


PROVIDERS = {
    # Google's OpenAI-compatible endpoint. GOOGLE_API_KEY is accepted because the
    # course's .env uses that name; Google's own docs use GEMINI_API_KEY.
    "gemini": Provider(
        name="gemini",
        key_vars=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        link_model="gemini-2.5-flash-lite",
        writer_model="gemini-2.8-flash",
    ),
    "openai": Provider(
        name="openai",
        key_vars=("OPENAI_API_KEY",),
        base_url=None,
        link_model="gpt-5-nano",
        writer_model="gpt-4.1-mini",
    ),
}
DEFAULT_PROVIDER = "gemini"


@dataclass(frozen=True)
class Settings:
    provider: str = DEFAULT_PROVIDER
    link_model: str = PROVIDERS[DEFAULT_PROVIDER].link_model
    writer_model: str = PROVIDERS[DEFAULT_PROVIDER].writer_model

    max_links: int = 6  # relevant pages to read besides the landing page
    max_candidate_links: int = 150  # links offered to the link-selection model
    context_token_budget: int = 6_000  # tokens of page text sent to the writer model
    fetch_concurrency: int = 4
    fetch_timeout_s: float = 15.0

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, provider: str | None = None
    ) -> Settings:
        """Provider from the argument, else BROCHURE_PROVIDER, else the default.
        Models come from BROCHURE_LINK_MODEL / BROCHURE_WRITER_MODEL, else the provider's defaults.
        """
        env = os.environ if env is None else env
        name = provider or env.get("BROCHURE_PROVIDER") or DEFAULT_PROVIDER
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider {name!r}; choose one of: {', '.join(PROVIDERS)}")
        defaults = PROVIDERS[name]
        return cls(
            provider=name,
            link_model=env.get("BROCHURE_LINK_MODEL") or defaults.link_model,
            writer_model=env.get("BROCHURE_WRITER_MODEL") or defaults.writer_model,
        )
