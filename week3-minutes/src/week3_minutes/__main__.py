"""python -m week3_minutes transcript.txt   (or --audio meeting.mp3)"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import openai
from dotenv import find_dotenv, load_dotenv

from labkit.providers import PROVIDERS, Provider, client_for, get_provider

from .config import Settings
from .minutes import (
    MinutesSettings,
    OpenAICompatibleLLM,
    make_minutes,
    render_markdown,
    usage_summary,
)
from .transcript import load


def connection_help(provider: Provider) -> str:
    if provider.name == "ollama":
        return (
            f"Couldn't reach Ollama at {provider.base_url}. Start it, then pull the model:\n"
            "  ollama serve        # or open the Ollama app\n"
            "  ollama pull llama3.2\n"
            "Or use a hosted open model: --provider huggingface (needs HF_TOKEN)."
        )
    return f"Couldn't reach {provider.name} at {provider.base_url or 'api.openai.com'}."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m week3_minutes", description="Meeting minutes from a transcript or audio."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("transcript", nargs="?", type=Path, help="A .txt transcript")
    source.add_argument("--audio", type=Path, help="An audio file (needs transformers)")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        help="Model provider (default: MINUTES_PROVIDER, else ollama)",
    )
    parser.add_argument("--title", default="Meeting minutes")
    parser.add_argument("--out", type=Path, help="Also save the minutes to this file")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    load_dotenv(find_dotenv(usecwd=True))

    try:
        settings = Settings.from_env(provider=args.provider)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    provider = get_provider(settings.provider)
    api_key = provider.api_key(os.environ)
    if not api_key:
        print(provider.missing_key_message(), file=sys.stderr)
        return 2

    if args.audio:
        from .transcribe import TranscriptionUnavailable, transcribe

        try:
            text = transcribe(args.audio)
        except TranscriptionUnavailable as exc:
            print(exc, file=sys.stderr)
            return 2
    else:
        if not args.transcript.is_file():
            print(f"No such file: {args.transcript}", file=sys.stderr)
            return 2
        text = load(args.transcript)

    llm = OpenAICompatibleLLM(client_for(provider, api_key, max_retries=2), settings.model)
    try:
        minutes = asyncio.run(make_minutes(llm, text, title=args.title, settings=MinutesSettings()))
    except openai.APIConnectionError:
        print(connection_help(provider), file=sys.stderr)
        return 1
    except openai.NotFoundError as exc:
        print(f"Model {settings.model!r} not found on {provider.name}: {exc}", file=sys.stderr)
        return 1
    except openai.OpenAIError as exc:
        print(f"{provider.name} API error: {exc}", file=sys.stderr)
        return 1

    markdown = render_markdown(minutes)
    print(markdown)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
        print(f"Saved to {args.out}", file=sys.stderr)
    print(f"{settings.provider} / {settings.model}: {usage_summary(llm)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
