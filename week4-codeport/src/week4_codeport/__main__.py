"""python -m week4_codeport --models gemini-3.8-flash,gemini-3.5-flash-lite"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import openai
from dotenv import find_dotenv, load_dotenv

from labkit.providers import PROVIDERS, client_for, get_provider

from .benchmarks import BENCHMARKS
from .evaluate import Evaluation, evaluate_cpp, reference_outputs, time_python
from .port import port
from .report import leaderboard
from .runner import DEFAULT_FLAGS, find_compiler

DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash,gemini-3.5-flash-lite",
    "openai": "gpt-5-nano,gpt-4.1-mini",
    "ollama": "qwen2.5-coder",
    "huggingface": "Qwen/Qwen2.5-Coder-32B-Instruct",
}

WARNING = (
    "Note: this compiles and runs code written by a model on your machine, with time "
    "and resource limits but no full sandbox."
)


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m week4_codeport",
        description="Port a Python benchmark to C++ with several models; check and time each.",
    )
    parser.add_argument("--benchmark", choices=sorted(BENCHMARKS), default="max_subarray")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        help="Model provider (default: CODEPORT_PROVIDER, else gemini)",
    )
    parser.add_argument("--models", help="Comma-separated model names for the provider")
    parser.add_argument(
        "--cpp",
        type=Path,
        action="append",
        default=[],
        help="Also check an existing .cpp file (repeatable); no model needed",
    )
    parser.add_argument(
        "--size",
        choices=("quick", "full"),
        default="quick",
        help="Timing input: quick (seconds) or full (the course's, slow in Python)",
    )
    parser.add_argument("--runs", type=int, default=3, help="Timed runs per program (median)")
    parser.add_argument("--save-code", type=Path, help="Folder to save each model's C++")
    parser.add_argument("--out", type=Path, help="Also save the leaderboard to this file")
    return parser.parse_args(argv)


async def _ports(provider_name: str, models: list[str], benchmark, compiler: str):
    provider = get_provider(provider_name)
    api_key = provider.api_key(os.environ)
    if not api_key:
        raise SystemExit(provider.missing_key_message())
    async with client_for(provider, api_key) as client:
        results = await asyncio.gather(
            *(port(client, m, benchmark, compiler) for m in models), return_exceptions=True
        )
    return list(zip(models, results, strict=True))


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    load_dotenv(find_dotenv(usecwd=True))
    compiler = find_compiler()
    if compiler is None:
        print(
            "No C++ compiler found. Install one (macOS: xcode-select --install; "
            "Ubuntu: sudo apt install g++) or set CXX.",
            file=sys.stderr,
        )
        return 2
    benchmark = BENCHMARKS[args.benchmark]
    print(WARNING, file=sys.stderr)
    print(f"Compiler: {compiler} {' '.join(DEFAULT_FLAGS)}", file=sys.stderr)

    print("Running the Python reference on the check inputs...", file=sys.stderr)
    expected = reference_outputs(benchmark)
    print(f"Timing Python on the {args.size} input...", file=sys.stderr)
    python_seconds = time_python(benchmark, size=args.size, runs=1)

    sources: list[tuple[str, str]] = []
    for path in args.cpp:
        sources.append((path.name, path.read_text(encoding="utf-8")))

    use_models = args.models or not args.cpp
    if use_models:
        provider = args.provider or os.environ.get("CODEPORT_PROVIDER") or "gemini"
        try:
            get_provider(provider)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        models = [m.strip() for m in (args.models or DEFAULT_MODELS[provider]).split(",") if m]
        print(f"Asking {provider}: {', '.join(models)}", file=sys.stderr)
        try:
            ported = asyncio.run(_ports(provider, models, benchmark, compiler))
        except SystemExit as exc:
            print(exc, file=sys.stderr)
            return 2
        for model, result in ported:
            if isinstance(result, openai.OpenAIError):
                print(f"  {model}: API error: {result}", file=sys.stderr)
                continue
            if isinstance(result, BaseException):
                raise result
            sources.append((model, result.code))
            if args.save_code:
                args.save_code.mkdir(parents=True, exist_ok=True)
                safe = model.replace("/", "_").replace(":", "_")
                (args.save_code / f"{benchmark.name}-{safe}.cpp").write_text(result.code)
            tokens = (
                f"{result.prompt_tokens:,} in / {result.completion_tokens:,} out"
                if result.prompt_tokens is not None
                else "usage not reported"
            )
            print(f"  {model}: {tokens}", file=sys.stderr)

    evaluations: list[Evaluation] = []
    for label, code in sources:
        print(f"Checking {label}...", file=sys.stderr)
        evaluations.append(
            evaluate_cpp(
                label,
                code,
                benchmark,
                expected,
                compiler=compiler,
                size=args.size,
                runs=args.runs,
                python_seconds=python_seconds,
            )
        )

    report = leaderboard(
        evaluations, benchmark=benchmark.name, size=args.size, python_seconds=python_seconds
    )
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Saved to {args.out}", file=sys.stderr)
    return 0 if any(e.correct for e in evaluations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
