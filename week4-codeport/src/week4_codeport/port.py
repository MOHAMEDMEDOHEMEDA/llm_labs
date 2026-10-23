"""Ask a model to port the Python program to C++, and pull the code out of its reply."""

from __future__ import annotations

import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from .benchmarks import Benchmark
from .runner import DEFAULT_FLAGS

SYSTEM_PROMPT = """\
You port Python programs to fast, correct C++17.
Reply with one complete C++ source file in a ```cpp code block and nothing else."""

_FENCE = re.compile(r"```[ \t]*([\w+#-]*)[^\n]*\n(.*?)```", re.S)


def user_prompt(benchmark: Benchmark, compiler: str) -> str:
    flags = " ".join(DEFAULT_FLAGS)
    example = " ".join(benchmark.example_args)
    return f"""\
Port this Python program to C++ so that it runs as fast as possible.

Requirements:
- It must print exactly the same output as the Python program, character for character, \
for any valid input. It will be tested on inputs you have not seen.
- Read the inputs from the command line in the same order: {benchmark.usage}
  (for example: ./main {example}). Do not hard-code inputs or results.
- Use only the C++17 standard library. Single file. No timing output.
- It will be compiled with: {compiler} {flags} main.cpp -o main

```python
{benchmark.source}
```"""


def extract_cpp(reply: str) -> str:
    """The C++ code block from a reply. Prefers blocks tagged cpp/c++; falls back to
    the longest block, then to the whole reply."""
    blocks = [(lang.lower(), body) for lang, body in _FENCE.findall(reply)]
    tagged = [body for lang, body in blocks if lang in {"cpp", "c++", "cxx", "cc"}]
    candidates = tagged or [body for _, body in blocks]
    if candidates:
        return max(candidates, key=len).strip() + "\n"
    return reply.strip() + "\n"


@dataclass(frozen=True)
class PortResult:
    model: str
    code: str
    prompt_tokens: int | None
    completion_tokens: int | None


async def port(client: AsyncOpenAI, model: str, benchmark: Benchmark, compiler: str) -> PortResult:
    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(benchmark, compiler)},
        ],
    )
    usage = completion.usage
    return PortResult(
        model=model,
        code=extract_cpp(completion.choices[0].message.content or ""),
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
    )
