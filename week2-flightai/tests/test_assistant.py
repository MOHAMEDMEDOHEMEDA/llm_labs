import json

from week2_flightai.assistant import FALLBACK_REPLY, Assistant, normalise_history
from week2_flightai.config import SYSTEM_PROMPT
from week2_flightai.tools import flight_tools


def assistant(store, model, rounds=4):
    return Assistant(model, flight_tools(store), SYSTEM_PROMPT, max_tool_rounds=rounds)


async def test_plain_answer_needs_one_call(store, scripted, turns):
    model = scripted([turns.text("Hello! How can I help?")])

    reply = await assistant(store, model).reply([], "hi")

    assert reply.text == "Hello! How can I help?"
    assert reply.model_calls == 1 and reply.tool_results == []
    sent, tools = model.requests[0]
    assert sent[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert sent[-1] == {"role": "user", "content": "hi"}
    assert {t["function"]["name"] for t in tools} >= {"get_ticket_price"}


async def test_tool_results_reach_the_model_before_it_answers(store, scripted, turns):
    model = scripted(
        [
            turns.tool(("get_ticket_price", {"destination_city": "London"})),
            turns.text("A return ticket to London is $799."),
        ]
    )

    reply = await assistant(store, model).reply([], "How much is London?")

    assert reply.text == "A return ticket to London is $799."
    second_request, _ = model.requests[1]
    tool_message = second_request[-1]
    assert tool_message["role"] == "tool" and tool_message["tool_call_id"] == "call_0"
    assert json.loads(tool_message["content"])["return_fare_usd"] == 799
    assert second_request[-2]["tool_calls"][0]["function"]["name"] == "get_ticket_price"


async def test_several_calls_in_one_turn_each_get_a_reply(store, scripted, turns):
    model = scripted(
        [
            turns.tool(
                ("get_ticket_price", {"destination_city": "Paris"}),
                ("get_ticket_price", {"destination_city": "Tokyo"}),
            ),
            turns.text("Paris is $899 and Tokyo is $1,420."),
        ]
    )

    reply = await assistant(store, model).reply([], "Paris or Tokyo?")

    tool_replies = [m for m in model.requests[1][0] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_replies] == ["call_0", "call_1"]
    assert len(reply.tool_results) == 2


async def test_the_loop_stops_at_the_limit_and_still_answers(store, scripted, turns):
    looping = [turns.tool(("list_destinations", {})) for _ in range(2)]
    model = scripted([*looping, turns.text("We fly to five cities.")])

    reply = await assistant(store, model, rounds=2).reply([], "where do you fly?")

    assert reply.text == "We fly to five cities."
    assert reply.model_calls == 3
    assert model.requests[-1][1] is None  # last request offered no tools


async def test_tool_calls_after_the_limit_are_not_executed(store, scripted, turns):
    model = scripted(
        [
            turns.tool(("list_destinations", {})),
            turns.tool(("request_booking", {"destination_city": "Paris", "passenger_name": "X"})),
        ]
    )

    reply = await assistant(store, model, rounds=1).reply([], "book everything")

    assert reply.hit_tool_limit and reply.text == FALLBACK_REPLY
    assert store.pending() == []  # the ignored call created nothing


async def test_tool_errors_go_back_to_the_model_to_recover(store, scripted, turns):
    model = scripted(
        [
            turns.tool(("request_booking", {"destination_city": "Rome", "passenger_name": "Ali"})),
            turns.text(
                "Sorry, we don't fly to Rome. We serve Berlin, London, Paris, Sydney, Tokyo."
            ),
        ]
    )

    reply = await assistant(store, model).reply([], "Book Rome for Ali")

    assert not reply.tool_results[0].ok
    assert "don't fly to Rome" in model.requests[1][0][-1]["content"]
    assert reply.text.startswith("Sorry")


async def test_empty_model_answer_gets_a_fallback(store, scripted, turns):
    reply = await assistant(store, scripted([turns.text("   ")])).reply([], "?")
    assert reply.text == FALLBACK_REPLY


def test_gradio_history_is_reduced_to_text_messages():
    history = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "file", "file": {"path": "x.png"}},
            ],
        },
        {"role": "system", "content": "ignored"},
        {"role": "assistant", "content": "   "},
    ]
    assert normalise_history(history) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
