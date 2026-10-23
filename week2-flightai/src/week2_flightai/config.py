"""Settings for the FlightAI assistant."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit.providers import get_provider

# A capable model for tool use on each provider. Override with FLIGHTAI_MODEL.
DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash",
    "openai": "gpt-4.1-mini",
    "ollama": "llama3.2",
    "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
}

SYSTEM_PROMPT = """\
You are the customer support assistant for FlightAI, an airline.
Give short, courteous answers of one or two sentences.

Rules:
- Quote fares only from the get_ticket_price tool. Never guess or remember a price.
- If a city is not served, say so and mention the cities we do serve.
- To book, you need the destination and the passenger's full name; ask for anything missing.
- request_booking only creates a pending booking. Tell the customer to press \
"Confirm booking" to complete it. Never say a flight is booked or confirmed.
- If a tool returns an error, explain the problem plainly and say what the customer can do.
- If you don't know something, say so."""


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    db_path: Path
    max_tool_rounds: int = 4

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, provider: str | None = None
    ) -> Settings:
        env = os.environ if env is None else env
        name = get_provider(provider or env.get("FLIGHTAI_PROVIDER") or "gemini").name
        return cls(
            provider=name,
            model=env.get("FLIGHTAI_MODEL") or DEFAULT_MODELS[name],
            db_path=Path(env.get("FLIGHTAI_DB") or "output/flightai.db"),
        )
