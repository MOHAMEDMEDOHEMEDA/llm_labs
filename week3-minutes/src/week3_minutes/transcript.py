"""Load a transcript and split long ones into parts that fit a small model's context."""

from __future__ import annotations

from pathlib import Path


def estimate_tokens(text: str) -> int:
    """About 4 characters per token for English. Open models use different tokenizers,
    so an estimate is all a budget needs; it avoids downloading a tokenizer."""
    return max(1, len(text) // 4)


def load(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def split(text: str, max_tokens: int, overlap_lines: int = 2) -> list[str]:
    """Split on line boundaries so no speaker turn is cut in half. Each part repeats the
    last `overlap_lines` lines of the previous one, so a task agreed across the boundary
    keeps its context. A single line longer than the budget is cut by characters."""
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    lines: list[str] = []
    for line in text.splitlines():
        lines.extend(_cut(line, max_tokens))

    parts: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if current and estimate_tokens("\n".join([*current, line])) > max_tokens:
            parts.append(current)
            carried = current[-overlap_lines:] if overlap_lines else []
            current = carried if estimate_tokens("\n".join([*carried, line])) <= max_tokens else []
        current.append(line)
    if current:
        parts.append(current)
    return ["\n".join(part) for part in parts]


def _cut(line: str, max_tokens: int) -> list[str]:
    width = max_tokens * 4
    return [line[i : i + width] for i in range(0, len(line), width)] or [line]
