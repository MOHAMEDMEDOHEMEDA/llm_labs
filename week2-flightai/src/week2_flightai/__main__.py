"""Run the FlightAI assistant: python -m week2_flightai"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import find_dotenv, load_dotenv

from labkit.providers import PROVIDERS, client_for, get_provider

from .app import build_ui
from .assistant import Assistant, OpenAIChatModel
from .config import SYSTEM_PROMPT, Settings
from .store import FareStore
from .tools import flight_tools


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m week2_flightai", description="FlightAI customer support assistant."
    )
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        help="Model provider (default: FLIGHTAI_PROVIDER, else gemini)",
    )
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("-v", "--verbose", action="store_true", help="Log each tool call")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
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

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    store = FareStore(settings.db_path)
    store.seed()
    assistant = Assistant(
        OpenAIChatModel(client_for(provider, api_key), settings.model),
        flight_tools(store),
        SYSTEM_PROMPT,
        max_tool_rounds=settings.max_tool_rounds,
    )
    print(f"FlightAI on {settings.provider} ({settings.model}); bookings in {settings.db_path}")
    # Local only: server_name 127.0.0.1 keeps it off your network; no public share link.
    build_ui(assistant, store).launch(
        server_name="127.0.0.1", server_port=args.port, inbrowser=True
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
