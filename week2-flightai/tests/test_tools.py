import json

from week2_flightai.tools import flight_tools


def run(store, name, args):
    result = flight_tools(store).execute(name, args if isinstance(args, str) else json.dumps(args))
    return result.ok, json.loads(result.content)


def test_specs_come_from_the_pydantic_models_without_provider_unfriendly_keys(store):
    specs = {s["function"]["name"]: s["function"] for s in flight_tools(store).specs()}

    assert set(specs) == {"get_ticket_price", "list_destinations", "request_booking"}
    booking = specs["request_booking"]["parameters"]
    assert booking["type"] == "object"
    assert booking["required"] == ["destination_city", "passenger_name"]
    assert set(booking["properties"]) == {"destination_city", "passenger_name"}
    flat = json.dumps(specs)
    assert '"title"' not in flat and "additionalProperties" not in flat
    assert specs["list_destinations"]["parameters"] == {"type": "object", "properties": {}}


def test_price_lookup_returns_the_fare_or_the_cities_we_serve(store):
    assert run(store, "get_ticket_price", {"destination_city": "berlin"}) == (
        True,
        {"found": True, "city": "Berlin", "return_fare_usd": 499},
    )
    ok, payload = run(store, "get_ticket_price", {"destination_city": "Rome"})
    assert ok and payload["found"] is False and "Tokyo" in payload["destinations_we_serve"]


def test_request_booking_creates_only_a_pending_booking(store):
    ok, payload = run(
        store, "request_booking", {"destination_city": "Sydney", "passenger_name": "Omar Adel"}
    )

    assert ok and payload["status"] == "pending_confirmation"
    assert store.booking(payload["booking_ref"]).status == "pending"


def test_bad_calls_become_readable_errors_instead_of_crashes(store):
    cases = [
        ("unknown_tool", "{}", "Unknown tool 'unknown_tool'"),
        ("get_ticket_price", "{not json", "not valid JSON"),
        ("get_ticket_price", {}, "destination_city: Field required"),
        (
            "get_ticket_price",
            {"destination_city": "Paris", "discount": 50},
            "discount: Extra inputs are not permitted",
        ),
        (
            "request_booking",
            {"destination_city": "Rome", "passenger_name": "Ali"},
            "don't fly to Rome",
        ),
    ]
    for name, args, expected in cases:
        ok, payload = run(store, name, args)
        assert not ok
        assert expected in payload["error"], (name, payload)


def test_a_crashing_handler_is_contained(store, monkeypatch):
    def boom(_city):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(store, "fare", boom)
    ok, payload = run(store, "get_ticket_price", {"destination_city": "Paris"})
    assert not ok and "failed unexpectedly" in payload["error"]
    assert "disk on fire" not in payload["error"]  # internals are not shown to the model
