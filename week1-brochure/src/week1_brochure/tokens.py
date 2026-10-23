"""Token counting for budgeting the writer prompt."""

from __future__ import annotations

from typing import Protocol

import tiktoken


class Tokenizer(Protocol):
    def count(self, text: str) -> int: ...

    def truncate(self, text: str, max_tokens: int) -> str: ...


class TiktokenTokenizer:
    """o200k_base is the encoding of recent OpenAI models.

    For other providers' models the counts are an estimate, which is fine for
    budgeting but not for billing.
    """

    def __init__(self, encoding_name: str = "o200k_base") -> None:
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text, disallowed_special=()))

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        tokens = self._encoding.encode(text, disallowed_special=())
        if len(tokens) <= max_tokens:
            return text
        return self._encoding.decode(tokens[:max_tokens])
