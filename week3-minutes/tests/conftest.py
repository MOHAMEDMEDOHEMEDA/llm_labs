"""Test doubles for week 3: no network, no model downloads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from week3_minutes.transcript import load

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "product-sync.txt"


class ScriptedLLM:
    """Returns queued replies (str, or dict which is sent as JSON) and records requests."""

    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.requests: list[list[dict[str, str]]] = []

    async def chat(self, messages):
        self.requests.append([dict(m) for m in messages])
        reply = self.replies.pop(0)
        return reply if isinstance(reply, str) else json.dumps(reply)


@pytest.fixture
def scripted():
    return ScriptedLLM


@pytest.fixture
def transcript() -> str:
    return load(SAMPLE)
