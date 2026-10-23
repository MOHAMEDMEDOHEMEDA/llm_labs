"""Test doubles for week 2: no test here calls a network or a paid API."""

from __future__ import annotations

import json

import pytest

from week2_flightai.assistant import ModelTurn, ToolCall
from week2_flightai.store import FareStore


@pytest.fixture
def store(tmp_path) -> FareStore:
    fares = FareStore(tmp_path / "fares.db")
    fares.seed()
    return fares


def text_turn(text: str) -> ModelTurn:
    return ModelTurn(text=text, tool_calls=[], message={"role": "assistant", "content": text})


def tool_turn(*calls: tuple[str, dict], text: str = "") -> ModelTurn:
    tool_calls = [
        ToolCall(f"call_{i}", name, json.dumps(args)) for i, (name, args) in enumerate(calls)
    ]
    message = {
        "role": "assistant",
        "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in tool_calls
        ],
    }
    return ModelTurn(text=text, tool_calls=tool_calls, message=message)


class ScriptedModel:
    """Plays back a list of turns and records what it was sent."""

    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = list(turns)
        self.requests: list[tuple[list[dict], list[dict] | None]] = []

    async def respond(self, messages, tools):
        self.requests.append(([dict(m) for m in messages], tools))
        return self.turns.pop(0)


@pytest.fixture
def scripted():
    return ScriptedModel


class Turns:
    text = staticmethod(text_turn)
    tool = staticmethod(tool_turn)


@pytest.fixture
def turns() -> type[Turns]:
    return Turns
