"""Check the model's claims against the transcript.

Every decision and action item must quote the transcript. A quote that isn't there, or an
owner whose name never appears, is moved to "needs checking" instead of being presented
as fact. This is the same idea as week 1's check on URLs: the model may only point at
things that exist in the source.
"""

from __future__ import annotations

import re
import string

MIN_QUOTE_CHARS = 12
_SPEAKER_PREFIX = re.compile(r"^\s*[\w .'-]{1,40}:\s+")  # "Karim: ..." copied from a line
# ASCII punctuation plus curly quotes and dashes.
_PUNCT = str.maketrans(
    {c: " " for c in string.punctuation + "\u201c\u201d\u2018\u2019\u2014\u2013"}
)


def normalise(text: str) -> str:
    return " ".join(text.lower().translate(_PUNCT).split())


class Grounding:
    def __init__(self, transcript: str) -> None:
        self._text = f" {normalise(transcript)} "

    def quote_problem(self, quote: str) -> str | None:
        clean = normalise(_SPEAKER_PREFIX.sub("", quote.strip("\"\u201c\u201d' ")))
        if len(clean) < MIN_QUOTE_CHARS:
            return "evidence quote is too short to check"
        if f" {clean} " not in self._text:
            return "evidence quote not found in the transcript"
        return None

    def name_appears(self, name: str) -> bool:
        """True if every word of the name appears as a whole word in the transcript."""
        words = normalise(name).split()
        return bool(words) and all(f" {w} " in self._text for w in words)

    def owner_problem(self, owner: str) -> str | None:
        if normalise(owner) in {"we", "team", "everyone", "all", "someone"}:
            return "no single owner"
        if not self.name_appears(owner):
            return f"owner {owner!r} is not mentioned in the transcript"
        return None
