"""Step 1: let a small model pick the pages worth reading."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from .links import canonical
from .llm import LLM, LLMOutputError, Usage
from .models import LinkSelection, RelevantLink
from .prompts import LINK_SYSTEM_PROMPT, link_user_prompt

log = logging.getLogger(__name__)

ATTEMPTS = 2


async def select_links(
    llm: LLM,
    *,
    model: str,
    site_url: str,
    candidates: Sequence[str],
    max_links: int,
) -> tuple[list[RelevantLink], list[Usage]]:
    """Return the chosen links (only URLs that were actually offered) and the usage.

    If the model's answer is unusable twice, return no links: the brochure is
    then written from the landing page alone instead of failing the run.
    """
    if not candidates or max_links <= 0:
        return [], []

    user = link_user_prompt(site_url, candidates, max_links)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            selection, usage = await llm.parse(
                model=model, system=LINK_SYSTEM_PROMPT, user=user, schema=LinkSelection
            )
        except LLMOutputError as exc:
            log.warning("Link selection attempt %d/%d unusable: %s", attempt, ATTEMPTS, exc)
            continue
        return _keep_offered(selection.links, candidates, max_links), [usage]

    log.warning("Link selection failed; using the landing page only")
    return [], []


def _keep_offered(
    links: Sequence[RelevantLink], candidates: Sequence[str], max_links: int
) -> list[RelevantLink]:
    """Drop URLs the model invented or altered; keep the original spelling of real ones."""
    offered = {canonical(url): url for url in candidates}
    kept: list[RelevantLink] = []
    seen: set[str] = set()
    for link in links:
        key = canonical(link.url)
        if key not in offered:
            log.info("Dropped a URL that was not in the candidate list: %s", link.url)
            continue
        if key in seen:
            continue
        seen.add(key)
        kept.append(RelevantLink(type=link.type, url=offered[key]))
        if len(kept) >= max_links:
            break
    return kept
