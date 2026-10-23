"""A thin LLM interface so the pipeline can be tested without calling an API."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import openai
import pydantic
from openai import AsyncOpenAI

from .config import Provider

T = TypeVar("T", bound=pydantic.BaseModel)

log = logging.getLogger(__name__)

# The SDK retries 408/409/429/5xx with exponential backoff (0.5 s doubling, 8 s cap).
# Its default of 2 retries gives up after about a second, too short for a capacity spike.
DEFAULT_MAX_RETRIES = 5


@dataclass(frozen=True)
class Usage:
    model: str  # the model that served the request, as reported by the API
    prompt_tokens: int | None  # None when the provider didn't report usage
    completion_tokens: int | None


class LLMOutputError(Exception):
    """The model answered, but not in a usable form: refusal, cut off, or invalid schema."""


class LLM(Protocol):
    async def parse(
        self, *, model: str, system: str, user: str, schema: type[T]
    ) -> tuple[T, Usage]: ...

    async def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> tuple[str, Usage]: ...


def _messages(system: str, user: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _usage(model: str, usage: Any) -> Usage:
    if usage is None:
        return Usage(model, None, None)
    return Usage(model, usage.prompt_tokens, usage.completion_tokens)


def client_for(provider: Provider, api_key: str, **kwargs: Any) -> AsyncOpenAI:
    """An OpenAI SDK client pointed at the provider's OpenAI-compatible endpoint."""
    kwargs.setdefault("max_retries", DEFAULT_MAX_RETRIES)
    return AsyncOpenAI(api_key=api_key, base_url=provider.base_url, **kwargs)


class OpenAILLM:
    """Works with any OpenAI-compatible endpoint (OpenAI, Gemini).

    API errors (auth, rate limits after the SDK's own retries, network) propagate
    unchanged; only unusable answers become LLMOutputError."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def parse(
        self, *, model: str, system: str, user: str, schema: type[T]
    ) -> tuple[T, Usage]:
        try:
            completion = await self._client.chat.completions.parse(
                model=model, messages=_messages(system, user), response_format=schema
            )
        except (
            openai.LengthFinishReasonError,
            openai.ContentFilterFinishReasonError,
            pydantic.ValidationError,
        ) as exc:
            raise LLMOutputError(f"{type(exc).__name__}: {exc}") from exc
        except openai.APIError:
            log.warning("Request to %s failed (link selection)", model)
            raise

        message = completion.choices[0].message
        if message.refusal:
            raise LLMOutputError(f"model refused: {message.refusal}")
        if message.parsed is None:
            raise LLMOutputError("model returned no parsed output")
        return message.parsed, _usage(completion.model, completion.usage)

    async def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> tuple[str, Usage]:
        try:
            if on_delta is None:
                completion = await self._client.chat.completions.create(
                    model=model, messages=_messages(system, user)
                )
                text = completion.choices[0].message.content or ""
                return text, _usage(completion.model, completion.usage)

            stream = await self._client.chat.completions.create(
                model=model,
                messages=_messages(system, user),
                stream=True,
                stream_options={"include_usage": True},  # final chunk carries token counts
            )
        except openai.APIError:
            log.warning("Request to %s failed (writing)", model)
            raise
        parts: list[str] = []
        served_model, usage = model, None
        async for chunk in stream:
            served_model = chunk.model or served_model
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    parts.append(delta)
                    on_delta(delta)
            if chunk.usage is not None:
                usage = chunk.usage
        return "".join(parts), _usage(served_model, usage)
