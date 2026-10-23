"""The whole run: landing page -> pick pages -> fetch them concurrently -> write."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from labkit.fetch import FetchError, Page

from .budget import Source, SourceReport, build_context
from .config import Settings
from .links import candidate_links
from .llm import LLM, Usage
from .prompts import writer_system_prompt, writer_user_prompt
from .selection import select_links
from .tokens import Tokenizer

Fetcher = Callable[[str], Awaitable[Page]]


@dataclass(frozen=True)
class FetchFailure:
    url: str
    reason: str


@dataclass(frozen=True)
class BrochureResult:
    markdown: str
    sources: list[SourceReport]  # what the writer model actually saw
    failures: list[FetchFailure]  # pages chosen but skipped
    usage: list[Usage]  # one entry per model call


async def generate_brochure(
    company: str,
    url: str,
    *,
    llm: LLM,
    fetch: Fetcher,
    tokenizer: Tokenizer,
    settings: Settings,
    tone: str = "professional",
    on_delta: Callable[[str], None] | None = None,
) -> BrochureResult:
    # Without the landing page there is nothing to write from, so this FetchError propagates.
    landing = await fetch(url)

    candidates = candidate_links(landing.links, landing.url, limit=settings.max_candidate_links)
    selected, usage = await select_links(
        llm,
        model=settings.link_model,
        site_url=landing.url,
        candidates=candidates,
        max_links=settings.max_links,
    )

    pages, failures = await _fetch_all(
        fetch, [link.url for link in selected], settings.fetch_concurrency
    )
    sources = [Source("Landing page", landing)]
    sources += [
        Source(f"{link.type.capitalize()} page", pages[link.url])
        for link in selected
        if link.url in pages
    ]
    context, reports = build_context(sources, tokenizer, settings.context_token_budget)

    markdown, writer_usage = await llm.complete(
        model=settings.writer_model,
        system=writer_system_prompt(tone),
        user=writer_user_prompt(company, context),
        on_delta=on_delta,
    )
    return BrochureResult(markdown, reports, failures, [*usage, writer_usage])


async def _fetch_all(
    fetch: Fetcher, urls: Sequence[str], concurrency: int
) -> tuple[dict[str, Page], list[FetchFailure]]:
    """Fetch pages concurrently. A page that fails is recorded and skipped;
    anything other than a FetchError is a bug and is re-raised."""
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(url: str) -> Page:
        async with semaphore:
            return await fetch(url)

    results = await asyncio.gather(*(fetch_one(url) for url in urls), return_exceptions=True)

    pages: dict[str, Page] = {}
    failures: list[FetchFailure] = []
    for url, result in zip(urls, results, strict=True):
        if isinstance(result, FetchError):
            failures.append(FetchFailure(url, result.reason))
        elif isinstance(result, BaseException):
            raise result
        elif not result.text.strip():
            # Typical of job boards and single-page apps that render with JavaScript.
            failures.append(FetchFailure(url, "no readable text (likely rendered by JavaScript)"))
        else:
            pages[url] = result
    return pages, failures
