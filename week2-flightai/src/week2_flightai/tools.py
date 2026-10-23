"""Tools the model may call, defined once as Pydantic models.

The course writes each tool's JSON schema by hand next to the function, so the two can
drift apart, and passes the model's arguments to the function unchecked. Here the schema
is generated from the same model that validates the arguments before anything runs.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .store import BookingError, FareStore

log = logging.getLogger(__name__)

# JSON-schema keys every provider accepts in tool parameters. Pydantic also emits "title"
# and "additionalProperties", which some function-calling backends have rejected; extra
# keys are refused by Pydantic's own validation instead.
_SCHEMA_KEYS = {
    "type",
    "description",
    "properties",
    "required",
    "enum",
    "items",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
}


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoArgs(_Args):
    pass


class PriceArgs(_Args):
    destination_city: str = Field(
        min_length=1, max_length=80, description="The city the customer wants to fly to."
    )


class BookingArgs(_Args):
    destination_city: str = Field(
        min_length=1, max_length=80, description="The city the customer wants to fly to."
    )
    passenger_name: str = Field(
        min_length=1,
        max_length=120,
        description="The passenger's full name, as given by the customer.",
    )


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[_Args]
    handler: Callable[[Any], dict[str, Any]]

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": _clean_schema(self.args.model_json_schema()),
            },
        }


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    content: str  # JSON text sent back to the model


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def specs(self) -> list[dict[str, Any]]:
        return [tool.spec() for tool in self._tools.values()]

    def execute(self, name: str, arguments: str) -> ToolResult:
        """Run one tool call. Every failure becomes a result the model can read and
        correct, so a bad call never crashes the conversation."""
        tool = self._tools.get(name)
        if tool is None:
            return _error(name, f"Unknown tool {name!r}. Available: {', '.join(self._tools)}.")
        try:
            raw = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return _error(name, "Arguments were not valid JSON.")
        try:
            args = tool.args.model_validate(raw)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors()
            )
            return _error(name, f"Invalid arguments: {problems}")
        try:
            payload = tool.handler(args)
        except BookingError as exc:
            return _error(name, str(exc))
        except Exception:
            log.exception("Tool %s failed", name)
            return _error(name, "The tool failed unexpectedly. Apologise and offer to try again.")
        return ToolResult(name, True, json.dumps(payload))


def flight_tools(store: FareStore) -> ToolRegistry:
    def get_ticket_price(args: PriceArgs) -> dict[str, Any]:
        price = store.fare(args.destination_city)
        if price is None:
            return {
                "found": False,
                "city": args.destination_city,
                "destinations_we_serve": store.destinations(),
            }
        return {"found": True, "city": args.destination_city.title(), "return_fare_usd": price}

    def list_destinations(_: NoArgs) -> dict[str, Any]:
        return {"destinations": store.destinations()}

    def request_booking(args: BookingArgs) -> dict[str, Any]:
        booking = store.request_booking(args.destination_city, args.passenger_name)
        return {
            "booking_ref": booking.ref,
            "status": "pending_confirmation",
            "city": booking.city.title(),
            "passenger": booking.passenger,
            "return_fare_usd": booking.price_usd,
            "next_step": "The customer must press 'Confirm booking' in the app. "
            "It is not booked until then.",
        }

    return ToolRegistry(
        [
            Tool(
                "get_ticket_price",
                "Get the return fare to a destination city.",
                PriceArgs,
                get_ticket_price,
            ),
            Tool(
                "list_destinations", "List every city FlightAI flies to.", NoArgs, list_destinations
            ),
            Tool(
                "request_booking",
                "Start a booking for a passenger. Creates a pending booking that the customer "
                "must confirm in the app; it does not book the flight by itself.",
                BookingArgs,
                request_booking,
            ),
        ]
    )


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in schema.items() if k in _SCHEMA_KEYS}
    if cleaned.get("type") == "object":
        properties = cleaned.get("properties", {})
        cleaned["properties"] = {k: _clean_schema(v) for k, v in properties.items()}
    if isinstance(cleaned.get("items"), dict):
        cleaned["items"] = _clean_schema(cleaned["items"])
    return cleaned


def _error(name: str, message: str) -> ToolResult:
    return ToolResult(name, False, json.dumps({"error": message}))
