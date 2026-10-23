"""Transcript -> verified minutes.

1. Split the transcript into parts that fit the model.
2. For each part, ask for JSON; if it can't be parsed or doesn't match the schema, show the
   model the problem and ask again (up to `repairs` times).
3. Merge the parts, check every quote and owner against the transcript, and combine the
   part summaries.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import ValidationError

from labkit.jsonparse import NoJSONObject, extract_json_object

from .grounding import Grounding, normalise
from .models import ActionItem, Decision, Minutes, PartNotes
from .prompts import (
    SUMMARY_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    part_prompt,
    repair_prompt,
    summary_prompt,
)
from .transcript import split

log = logging.getLogger(__name__)


class ChatLLM(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatibleLLM:
    """Ollama, the Hugging Face router, Gemini or OpenAI, all through one API.

    No `response_format` is sent: not every open-model server enforces schemas, so the
    reply is parsed and validated here instead."""

    def __init__(self, client: AsyncOpenAI, model: str, temperature: float = 0.0) -> None:
        self._client = client
        self.model = model
        self._temperature = temperature
        self.calls: list[tuple[int | None, int | None]] = []  # (prompt, completion) tokens

    async def chat(self, messages: list[dict[str, str]]) -> str:
        completion = await self._client.chat.completions.create(
            model=self.model, messages=messages, temperature=self._temperature
        )
        usage = completion.usage
        self.calls.append((usage.prompt_tokens, usage.completion_tokens) if usage else (None, None))
        return completion.choices[0].message.content or ""


@dataclass
class MinutesSettings:
    part_tokens: int = 1_500  # small enough for an 8B model with room for the reply
    overlap_lines: int = 2
    repairs: int = 2


@dataclass
class _PartResult:
    index: int
    notes: PartNotes | None
    attempts: int
    problems: list[str] = field(default_factory=list)


async def notes_for_part(
    llm: ChatLLM, part: str, index: int, total: int, repairs: int
) -> _PartResult:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": part_prompt(part, index, total)},
    ]
    result = _PartResult(index, None, 0)
    for _ in range(repairs + 1):
        result.attempts += 1
        reply = await llm.chat(messages)
        try:
            result.notes = PartNotes.model_validate(extract_json_object(reply))
            return result
        except NoJSONObject as exc:
            problem = str(exc)
        except ValidationError as exc:
            problem = "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5]
            )
        result.problems.append(problem)
        log.warning("Part %d attempt %d unusable: %s", index + 1, result.attempts, problem)
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": repair_prompt(problem)},
        ]
    return result


async def make_minutes(
    llm: ChatLLM, transcript: str, *, title: str, settings: MinutesSettings | None = None
) -> Minutes:
    settings = settings or MinutesSettings()
    parts = split(transcript, settings.part_tokens, settings.overlap_lines)
    results = [
        await notes_for_part(llm, part, i, len(parts), settings.repairs)
        for i, part in enumerate(parts)
    ]
    notes = [r.notes for r in results if r.notes is not None]
    failed = [r.index + 1 for r in results if r.notes is None]

    grounding = Grounding(transcript)
    decisions, items, needs_checking = _verify(notes, grounding)
    summary = await _combine_summaries(llm, [n.summary for n in notes])
    return Minutes(
        title=title,
        summary=summary,
        attendees=_attendees(notes, grounding),
        decisions=decisions,
        action_items=items,
        needs_checking=needs_checking,
        parts_failed=failed,
    )


def _verify(
    notes: Sequence[PartNotes], grounding: Grounding
) -> tuple[list[Decision], list[ActionItem], list[tuple[str, str]]]:
    decisions: dict[str, Decision] = {}
    items: dict[tuple[str, str], ActionItem] = {}
    needs_checking: dict[str, str] = {}
    for part in notes:
        for d in part.decisions:
            problem = grounding.quote_problem(d.evidence)
            if problem:
                needs_checking.setdefault(f"Decision: {d.decision}", problem)
            else:
                decisions.setdefault(normalise(d.decision), d)  # overlap repeats lines
        for a in part.action_items:
            problem = grounding.quote_problem(a.evidence) or grounding.owner_problem(a.owner)
            if problem:
                needs_checking.setdefault(f"Action: {a.owner}: {a.task}", problem)
            else:
                items.setdefault((normalise(a.owner), normalise(a.task)), a)
    return list(decisions.values()), list(items.values()), list(needs_checking.items())


def _attendees(notes: Sequence[PartNotes], grounding: Grounding) -> list[str]:
    seen: dict[str, str] = {}
    for part in notes:
        for name in part.attendees:
            if grounding.name_appears(name):
                seen.setdefault(normalise(name), name.strip())
    return sorted(seen.values(), key=str.lower)


async def _combine_summaries(llm: ChatLLM, summaries: list[str]) -> str:
    if not summaries:
        return "No summary: the model did not return usable notes."
    if len(summaries) == 1:
        return summaries[0]
    reply = await llm.chat(
        [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": summary_prompt(summaries)},
        ]
    )
    return reply.strip() or " ".join(summaries)


def render_markdown(minutes: Minutes) -> str:
    lines = [f"# {minutes.title}", "", "## Summary", "", minutes.summary, ""]
    lines += ["## Attendees", "", ", ".join(minutes.attendees) or "Not recorded.", ""]
    lines += ["## Decisions", ""]
    lines += [f"- {d.decision}" for d in minutes.decisions] or ["- None recorded."]
    lines += ["", "## Action items", "", "| Owner | Task | Due |", "|---|---|---|"]
    lines += [f"| {a.owner} | {a.task} | {a.due or '—'} |" for a in minutes.action_items]
    if not minutes.action_items:
        lines.append("| — | None recorded | — |")
    if minutes.needs_checking:
        lines += [
            "",
            "## Needs checking",
            "",
            "The model reported these, but its quote or owner wasn't found in the transcript.",
            "",
        ]
        lines += [f"- {item} ({reason})" for item, reason in minutes.needs_checking]
    if minutes.parts_failed:
        parts = ", ".join(map(str, minutes.parts_failed))
        lines += [
            "",
            f"> Part(s) {parts} of the transcript could not be processed and are "
            "missing from these minutes.",
        ]
    return "\n".join(lines) + "\n"


def usage_summary(llm: Any) -> str:
    calls = getattr(llm, "calls", [])
    if not calls:
        return "no model calls recorded"
    if any(p is None for p, _ in calls):
        return f"{len(calls)} model calls (token usage not reported by the server)"
    prompt = sum(p for p, _ in calls)
    completion = sum(c for _, c in calls)
    return f"{len(calls)} model calls, {prompt:,} prompt + {completion:,} completion tokens"
