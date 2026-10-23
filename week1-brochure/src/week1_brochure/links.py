"""Deterministic link filtering, done in code before the model sees anything.

The course asks the model to resolve relative links and skip legal pages. Code
does that reliably and for free; the model only makes the judgement call.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit

_EXCLUDED_WORDS = (
    "privacy",
    "terms",
    "cookie",
    "legal",
    "login",
    "log-in",
    "signin",
    "sign-in",
    "signup",
    "sign-up",
    "register",
    "password",
    "cart",
    "checkout",
)
_EXCLUDED_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".zip",
    ".mp3",
    ".mp4",
    ".xml",
    ".json",
    ".css",
    ".js",
)
# Careers pages often live on a hiring platform rather than the company's domain.
_JOB_BOARD_HOSTS = (
    "lever.co",
    "greenhouse.io",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
)


def canonical(url: str) -> str:
    """Comparison key: lower-case scheme and host, no trailing slash, no fragment."""
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def _bare_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def _within(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def candidate_links(links: Iterable[str], site_url: str, *, limit: int) -> list[str]:
    """Same-site (or job-board) links worth offering to the model, in page order."""
    site_host = _bare_host(urlsplit(site_url).hostname or "")
    seen = {canonical(site_url)}
    result: list[str] = []
    for url in links:
        parts = urlsplit(url)
        host = _bare_host(parts.hostname or "")
        if not (_within(host, site_host) or any(_within(host, b) for b in _JOB_BOARD_HOSTS)):
            continue
        path = parts.path.lower()
        if path.endswith(_EXCLUDED_EXTENSIONS) or any(word in path for word in _EXCLUDED_WORDS):
            continue
        key = canonical(url)
        if key in seen:
            continue
        seen.add(key)
        result.append(url)
        if len(result) >= limit:
            break
    return result
