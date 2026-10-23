"""Command line entry point: python -m week1_brochure "Company" https://company.com"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import openai
from dotenv import find_dotenv, load_dotenv

from labkit.fetch import FetchError, Page, RobotsPolicy, fetch_page, make_client

from .config import PROVIDERS, Settings
from .llm import OpenAILLM, client_for
from .pipeline import BrochureResult, generate_brochure
from .prompts import TONES
from .tokens import TiktokenTokenizer, Tokenizer


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m week1_brochure",
        description="Generate a short company brochure from the company's own website.",
    )
    parser.add_argument("company", help='Company name, e.g. "Hugging Face"')
    parser.add_argument("url", help="Company website, e.g. https://huggingface.co")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        help="Model provider (default: BROCHURE_PROVIDER, else gemini)",
    )
    parser.add_argument("--tone", choices=sorted(TONES), default="professional")
    parser.add_argument("--out", type=Path, help="Also save the brochure to this file")
    parser.add_argument("--no-stream", action="store_true", help="Print only when finished")
    parser.add_argument("--max-links", type=int, help="Pages to read besides the landing page")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug logging")
    return parser.parse_args(argv)


async def _run(
    args: argparse.Namespace, settings: Settings, tokenizer: Tokenizer, api_key: str
) -> BrochureResult:
    robots = RobotsPolicy()
    provider = PROVIDERS[settings.provider]
    async with (
        make_client(timeout=settings.fetch_timeout_s) as http,
        client_for(provider, api_key) as client,
    ):

        async def fetch(url: str) -> Page:
            return await fetch_page(http, url, robots=robots)

        def write_delta(text: str) -> None:
            sys.stdout.write(text)
            sys.stdout.flush()

        return await generate_brochure(
            args.company,
            args.url,
            llm=OpenAILLM(client),
            fetch=fetch,
            tokenizer=tokenizer,
            settings=settings,
            tone=args.tone,
            on_delta=None if args.no_stream else write_delta,
        )


def _report(result: BrochureResult) -> None:
    err = sys.stderr
    print("\n--- run report ---", file=err)
    print("Pages the writer saw:", file=err)
    for source in result.sources:
        note = " (truncated)" if source.truncated else ""
        print(
            f"  {source.label:<18} {source.tokens_kept:>6,}/{source.tokens_total:,} tokens"
            f"{note}  {source.url}",
            file=err,
        )
    if result.failures:
        print("Pages skipped:", file=err)
        for failure in result.failures:
            print(f"  {failure.url}  ({failure.reason})", file=err)
    print("Model calls:", file=err)
    for usage in result.usage:
        if usage.prompt_tokens is None:
            tokens = "token usage not reported by the provider"
        else:
            tokens = f"prompt {usage.prompt_tokens:>6,}  completion {usage.completion_tokens:>6,}"
        print(f"  {usage.model:<28} {tokens}", file=err)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    load_dotenv(find_dotenv(usecwd=True))  # .env from the directory you run in, or a parent

    try:
        settings = Settings.from_env(provider=args.provider)
    except ValueError as exc:  # e.g. a typo in BROCHURE_PROVIDER
        print(exc, file=sys.stderr)
        return 2
    provider = PROVIDERS[settings.provider]

    # Check presence only: key formats change, and the API reports invalid keys clearly.
    api_key = provider.api_key(os.environ)
    if not api_key:
        print(
            f"No API key for {provider.name}: set {' or '.join(provider.key_vars)}. "
            "Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        return 2
    if urlsplit(args.url).scheme not in ("http", "https"):
        print("The URL must start with http:// or https://", file=sys.stderr)
        return 2

    if args.max_links is not None:
        settings = replace(settings, max_links=args.max_links)

    # Fail before any paid call: tiktoken downloads its encoding file on first use.
    try:
        tokenizer = TiktokenTokenizer()
    except Exception as exc:  # network, proxy or cache problems all surface differently
        print(
            f"Could not load the tokenizer ({type(exc).__name__}). The first run downloads it "
            "from openaipublic.blob.core.windows.net; check your network or proxy.",
            file=sys.stderr,
        )
        return 1

    try:
        result = asyncio.run(_run(args, settings, tokenizer, api_key))
    except FetchError as exc:
        print(f"\nCould not fetch {exc.url}: {exc.reason}", file=sys.stderr)
        return 1
    except openai.OpenAIError as exc:
        # Gemini errors arrive through the same SDK, so this covers both providers.
        print(f"\n{provider.name} API error: {exc}", file=sys.stderr)
        return 1

    if args.no_stream:
        print(result.markdown)
    else:
        print()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result.markdown + "\n", encoding="utf-8")
        print(f"Saved to {args.out}", file=sys.stderr)
    _report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
