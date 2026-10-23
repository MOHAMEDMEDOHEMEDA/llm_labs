"""The real OpenAI SDK against a fake HTTP layer (httpx2 is the SDK's HTTP client)."""

import json

import httpx2
import openai

from labkit.providers import PROVIDERS, client_for
from week2_flightai.assistant import Assistant, OpenAIChatModel
from week2_flightai.config import SYSTEM_PROMPT
from week2_flightai.tools import flight_tools


def completion(message: dict, finish_reason: str) -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "gemini-3.8-flash",
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    }


TOOL_CALL = {
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "call_abc",
            "type": "function",
            "function": {"name": "get_ticket_price", "arguments": '{"destination_city": "Tokyo"}'},
            # Provider-specific data on a tool call must be sent back unchanged.
            "extra_content": {"google": {"thought_signature": "c2lnbmF0dXJl"}},
        }
    ],
}
ANSWER = {"role": "assistant", "content": "Tokyo is $1,420 return."}


async def test_full_tool_round_trip_through_the_sdk(store):
    replies = [completion(TOOL_CALL, "tool_calls"), completion(ANSWER, "stop")]
    requests: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json=replies.pop(0))

    http = openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    client = client_for(PROVIDERS["gemini"], "k", http_client=http, max_retries=0)
    bot = Assistant(OpenAIChatModel(client, "gemini-3.8-flash"), flight_tools(store), SYSTEM_PROMPT)

    reply = await bot.reply([], "How much to Tokyo?")

    assert reply.text == "Tokyo is $1,420 return."
    first, second = requests
    assert first["model"] == "gemini-3.8-flash"
    assert {t["function"]["name"] for t in first["tools"]} == {
        "get_ticket_price",
        "list_destinations",
        "request_booking",
    }
    echoed = second["messages"][-2]["tool_calls"][0]
    assert echoed["extra_content"] == {"google": {"thought_signature": "c2lnbmF0dXJl"}}
    tool_reply = second["messages"][-1]
    assert tool_reply == {
        "role": "tool",
        "tool_call_id": "call_abc",
        "content": json.dumps({"found": True, "city": "Tokyo", "return_fare_usd": 1420}),
    }


async def test_missing_tool_call_ids_are_filled_in_consistently(store):
    no_id = json.loads(json.dumps(TOOL_CALL))
    del no_id["tool_calls"][0]["id"]
    replies = [completion(no_id, "tool_calls"), completion(ANSWER, "stop")]
    requests: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json=replies.pop(0))

    http = openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    client = client_for(PROVIDERS["gemini"], "k", http_client=http, max_retries=0)
    bot = Assistant(OpenAIChatModel(client, "m"), flight_tools(store), SYSTEM_PROMPT)

    await bot.reply([], "Tokyo?")

    sent = requests[1]["messages"]
    assert sent[-2]["tool_calls"][0]["id"] == sent[-1]["tool_call_id"] == "call_0"
