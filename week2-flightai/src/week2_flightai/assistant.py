"""The tool-calling loop.

The course loops `while finish_reason == "tool_calls"`, which never ends if the model
keeps calling tools. This loop has a hard limit: after `max_tool_rounds` it asks once
more with tools switched off, so the customer always gets an answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI

from .tools import ToolRegistry, ToolResult

log = logging.getLogger(__name__)

FALLBACK_REPLY = "Sorry, I couldn't answer that. Could you rephrase?"


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ModelTurn:
    text: str
    tool_calls: list[ToolCall]
    # The assistant message exactly as the API returned it. It is sent back unchanged,
    # because some providers attach data to tool calls (Gemini's thought signatures,
    # for example) that must round-trip.
    message: dict[str, Any]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ChatModel(Protocol):
    async def respond(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> ModelTurn: ...


class OpenAIChatModel:
    """Any OpenAI-compatible Chat Completions endpoint (Gemini, OpenAI, Ollama...)."""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self.model = model

    async def respond(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> ModelTurn:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        completion = await self._client.chat.completions.create(**kwargs)
        message = completion.choices[0].message
        calls = [
            ToolCall(call.id or f"call_{i}", call.function.name, call.function.arguments)
            for i, call in enumerate(message.tool_calls or [])
            if call.type == "function"
        ]
        raw = message.model_dump(exclude_none=True)
        for i, call in enumerate(raw.get("tool_calls", [])):
            call.setdefault("id", f"call_{i}")  # keep ids consistent with the tool replies
        usage = completion.usage
        return ModelTurn(
            text=message.content or "",
            tool_calls=calls,
            message=raw,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )


@dataclass
class Reply:
    text: str
    tool_results: list[ToolResult] = field(default_factory=list)
    model_calls: int = 0
    hit_tool_limit: bool = False


class Assistant:
    def __init__(
        self, model: ChatModel, tools: ToolRegistry, system_prompt: str, max_tool_rounds: int = 4
    ) -> None:
        self._model = model
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_rounds = max_tool_rounds

    async def reply(self, history: list[dict[str, Any]], user_message: str) -> Reply:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
            *normalise_history(history),
            {"role": "user", "content": user_message},
        ]
        result = Reply(text="")
        for round_number in range(self._max_rounds + 1):
            tools_allowed = round_number < self._max_rounds
            turn = await self._model.respond(
                messages, self._tools.specs() if tools_allowed else None
            )
            result.model_calls += 1
            if not turn.tool_calls:
                result.text = turn.text.strip() or FALLBACK_REPLY
                return result
            if not tools_allowed:  # the model ignored "no tools"; don't run them
                break
            messages.append(turn.message)
            for call in turn.tool_calls:
                outcome = self._tools.execute(call.name, call.arguments)
                result.tool_results.append(outcome)
                log.info("tool %s ok=%s", call.name, outcome.ok)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": outcome.content}
                )
        result.hit_tool_limit = True
        result.text = FALLBACK_REPLY
        return result


def normalise_history(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Gradio 6 chat history -> plain chat messages.

    Gradio may give content as a string or as a list of parts such as
    {"type": "text", "text": "..."}; only text is kept, and only user/assistant turns.
    """
    messages = []
    for item in history:
        role = item.get("role")
        if role not in ("user", "assistant"):
            continue
        content = item.get("content")
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    return messages
