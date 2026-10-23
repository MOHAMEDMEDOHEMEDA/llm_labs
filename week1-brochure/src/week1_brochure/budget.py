"""Fit several pages into one prompt without silently dropping any of them.

The course joins every page and then cuts the string at 5,000 characters, so
pages near the end (often About or Careers) can vanish entirely. Here each page
gets a share of a token budget instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from labkit.fetch import Page

from .tokens import Tokenizer


def allocate(sizes: Sequence[int], budget: int) -> list[int]:
    """Split `budget` tokens across sources of the given sizes ("water-filling").

    Short sources keep everything; the rest is shared equally among longer ones.
    Every allocation is <= its source's size, and the total is <= budget.
    """
    allocation = [0] * len(sizes)
    if budget <= 0 or not sizes:
        return allocation
    remaining = budget
    order = sorted(range(len(sizes)), key=lambda i: sizes[i])
    for position, index in enumerate(order):
        share = remaining // (len(sizes) - position)
        allocation[index] = min(sizes[index], share)
        remaining -= allocation[index]
    return allocation


@dataclass(frozen=True)
class Source:
    label: str
    page: Page


@dataclass(frozen=True)
class SourceReport:
    label: str
    url: str
    tokens_total: int
    tokens_kept: int

    @property
    def truncated(self) -> bool:
        return self.tokens_kept < self.tokens_total


def build_context(
    sources: Sequence[Source], tokenizer: Tokenizer, budget: int
) -> tuple[str, list[SourceReport]]:
    """Return the prompt text for all sources and a report of what each contributed.

    The budget covers page text; the short section headers are not counted.
    """
    sizes = [tokenizer.count(source.page.text) for source in sources]
    allocation = allocate(sizes, budget)

    sections: list[str] = []
    reports: list[SourceReport] = []
    for source, size, keep in zip(sources, sizes, allocation, strict=True):
        marker = " [truncated]" if keep < size else ""
        body = tokenizer.truncate(source.page.text, keep)
        sections.append(f"## {source.label}: {source.page.url}{marker}\n\n{body}")
        reports.append(SourceReport(source.label, source.page.url, size, keep))
    return "\n\n".join(sections), reports
