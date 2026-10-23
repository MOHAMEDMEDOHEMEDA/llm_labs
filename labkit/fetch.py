"""Bounded, polite web page fetching shared across projects.

Written for this repo to replace the course's scraper.py. Differences: async,
respects robots.txt, caps response size, identifies itself honestly, and returns
a typed Page instead of a pre-formatted string.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "llm-engineering-lab/0.1 (+https://github.com/islamIbrahim89/llm-engineering-lab)"
DEFAULT_MAX_BYTES = 2_000_000

_HTML_TYPES = ("text/html", "application/xhtml+xml")
# Navigation menus repeat on every page and waste the token budget.
_STRIP_TAGS = ["script", "style", "noscript", "svg", "img", "input", "template", "iframe", "nav"]


class FetchError(Exception):
    """A page could not be fetched or used. `reason` is short and safe to show users."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason


@dataclass(frozen=True)
class Page:
    url: str  # final URL, after redirects
    title: str
    text: str
    links: tuple[str, ...]  # absolute http(s) links, fragments removed, de-duplicated


def make_client(timeout: float = 15.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=timeout,
        follow_redirects=True,
        max_redirects=5,
    )


def parse_html(html: str, base_url: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        absolute, _fragment = urldefrag(urljoin(base_url, str(anchor["href"]).strip()))
        if urlsplit(absolute).scheme not in ("http", "https") or absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)

    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    text = (soup.body or soup).get_text("\n", strip=True)
    return Page(url=base_url, title=title, text=text, links=tuple(links))


class RobotsPolicy:
    """Caches robots.txt per origin.

    Follows RFC 9309: a 4xx response means no restrictions; a 5xx response or an
    unreachable server means assume everything is disallowed.
    """

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self._user_agent = user_agent
        # origin -> (parsed rules, or the reason every URL there is blocked)
        self._rules: dict[str, RobotFileParser | str] = {}
        self._lock = asyncio.Lock()

    async def blocked_reason(self, client: httpx.AsyncClient, url: str) -> str | None:
        """None if `url` may be fetched, otherwise a short reason."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        async with self._lock:
            rules = self._rules.get(origin)
            if rules is None:
                rules = await self._load(client, origin)
                self._rules[origin] = rules
        if isinstance(rules, str):
            return rules
        return None if rules.can_fetch(self._user_agent, url) else "disallowed by robots.txt"

    @staticmethod
    async def _load(client: httpx.AsyncClient, origin: str) -> RobotFileParser | str:
        try:
            response = await client.get(f"{origin}/robots.txt")
        except httpx.HTTPError as exc:
            return f"robots.txt unreachable ({type(exc).__name__}), so not fetching"
        if response.status_code >= 500:
            return f"robots.txt returned HTTP {response.status_code}, so not fetching"
        parser = RobotFileParser()
        if response.status_code >= 400:
            parser.allow_all = True
        else:
            parser.parse(response.text.splitlines())
        return parser


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    *,
    robots: RobotsPolicy | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Page:
    """Fetch one HTML page. Raises FetchError for anything that makes the page unusable."""
    if robots is not None and (reason := await robots.blocked_reason(client, url)):
        raise FetchError(url, reason)

    try:
        async with client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise FetchError(url, f"HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type not in _HTML_TYPES:
                raise FetchError(url, f"not an HTML page ({content_type or 'no content type'})")

            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) >= max_bytes:  # keep what fits; very large pages are rarely useful
                    del body[max_bytes:]
                    break
            encoding = response.charset_encoding or "utf-8"
            final_url = str(response.url)
    except httpx.TimeoutException as exc:
        raise FetchError(url, "timed out") from exc
    except httpx.HTTPError as exc:
        raise FetchError(url, f"network error ({type(exc).__name__})") from exc

    try:
        html = bytes(body).decode(encoding, errors="replace")
    except LookupError:  # server declared a charset Python doesn't know
        html = bytes(body).decode("utf-8", errors="replace")
    return parse_html(html, final_url)
