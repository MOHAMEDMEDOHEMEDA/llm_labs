"""Pull one JSON object out of a model reply.

Open models often wrap JSON in code fences or add a sentence before or after it, and
not every server can enforce a schema. This finds the first complete JSON object in the
text; validating its shape is the caller's job.
"""

from __future__ import annotations

import json
from typing import Any


class NoJSONObject(ValueError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    raise NoJSONObject("The reply contained no complete JSON object.")
