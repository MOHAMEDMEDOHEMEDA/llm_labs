"""Test doubles: no test in this folder calls a network or a paid API."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from labkit.fetch import FetchError, Page
from week1_brochure.llm import Usage


class WordTokenizer:
    """One token per whitespace-separated word: predictable numbers in tests."""

    def count(self, text: str) -> int:
        return len(text.split())

    def truncate(self, text: str, max_tokens: int) -> str:
        return " ".join(text.split()[: max(max_tokens, 0)])


class FakeLLM:
    """Returns queued answers for parse(); records calls to complete()."""

    def __init__(self, parse_results: list, text: str = "# Acme\n\nWe build rockets.") -> None:
        self.parse_results = list(parse_results)
        self.text = text
        self.parse_calls = 0
        self.complete_calls: list[dict] = []

    async def parse(self, *, model, system, user, schema):
        self.parse_calls += 1
        result = self.parse_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result, Usage(model, 100, 20)

    async def complete(self, *, model, system, user, on_delta=None):
        self.complete_calls.append({"model": model, "system": system, "user": user})
        if on_delta is not None:
            for piece in self.text.splitlines(keepends=True):
                on_delta(piece)
        return self.text, Usage(model, 500, 80)


def make_page(url: str, text: str = "", links: tuple[str, ...] = ()) -> Page:
    return Page(url=url, title="", text=text, links=links)


def make_fetcher(pages: dict[str, Page | Exception]) -> Callable:
    async def fetch(url: str) -> Page:
        result = pages.get(url, FetchError(url, "HTTP 404"))
        if isinstance(result, Exception):
            raise result
        return result

    return fetch


@pytest.fixture
def tokenizer() -> WordTokenizer:
    return WordTokenizer()


@pytest.fixture
def fake_llm() -> type[FakeLLM]:
    return FakeLLM


@pytest.fixture
def page() -> Callable[..., Page]:
    return make_page


@pytest.fixture
def fetcher() -> Callable[[dict], Callable]:
    return make_fetcher
