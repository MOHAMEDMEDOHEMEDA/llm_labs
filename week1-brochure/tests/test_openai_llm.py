"""Contract tests for the OpenAI adapter, run against the real SDK with a fake HTTP layer.

The SDK (openai 3.x) sends requests through httpx2, so the mock transport comes
from httpx2. If an SDK upgrade changes that, these tests are the ones to update.
"""

import json

import httpx2
import openai
import pytest

from week1_brochure.llm import LLMOutputError, OpenAILLM
from week1_brochure.models import LinkSelection

SERVED_MODEL = "gpt-5-nano-2025-08-07"


def completion(content: str | None, *, finish_reason="stop", refusal=None) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": SERVED_MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content, "refusal": refusal},
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
    }


def llm_returning(response: httpx2.Response, seen: list | None = None) -> OpenAILLM:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        return response

    http = openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    client = openai.AsyncOpenAI(api_key="test-key", http_client=http, max_retries=0)
    return OpenAILLM(client)


async def parse_links(llm: OpenAILLM):
    return await llm.parse(model="gpt-5-nano", system="s", user="u", schema=LinkSelection)


async def test_parse_returns_validated_model_and_served_model_usage():
    answer = {"links": [{"type": "careers", "url": "https://acme.test/careers"}]}
    seen: list = []
    llm = llm_returning(httpx2.Response(200, json=completion(json.dumps(answer))), seen)

    selection, usage = await parse_links(llm)

    assert selection.links[0].url == "https://acme.test/careers"
    assert (usage.model, usage.prompt_tokens, usage.completion_tokens) == (SERVED_MODEL, 120, 30)
    # the request asked for a strict JSON schema, not plain JSON mode
    response_format = seen[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True


@pytest.mark.parametrize(
    "body",
    [
        completion(None, refusal="I can't help with that."),
        completion('{"links": [', finish_reason="length"),
        completion('{"links": [{"type": "not-a-type", "url": "x"}]}'),
    ],
    ids=["refusal", "cut-off", "schema-violation"],
)
async def test_unusable_answers_become_llm_output_errors(body):
    with pytest.raises(LLMOutputError):
        await parse_links(llm_returning(httpx2.Response(200, json=body)))


async def test_api_errors_are_not_disguised_as_output_errors():
    error = {"error": {"message": "bad key", "type": "invalid_request_error", "code": "x"}}
    with pytest.raises(openai.AuthenticationError):
        await parse_links(llm_returning(httpx2.Response(401, json=error)))


async def test_streaming_completion_forwards_deltas_and_reads_final_usage():
    def chunk(choices: list, usage: dict | None = None) -> str:
        data = {
            "id": "c",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": SERVED_MODEL,
            "choices": choices,
            "usage": usage,
        }
        return f"data: {json.dumps(data)}\n\n"

    def delta(text: str) -> list:
        return [{"index": 0, "delta": {"content": text}, "finish_reason": None}]

    body = (
        chunk(delta("# Acme"))
        + chunk(delta("\n\nRockets."))
        + chunk([], {"prompt_tokens": 900, "completion_tokens": 40, "total_tokens": 940})
        + "data: [DONE]\n\n"
    )
    response = httpx2.Response(
        200, content=body.encode(), headers={"content-type": "text/event-stream"}
    )
    received: list[str] = []

    text, usage = await llm_returning(response).complete(
        model="gpt-4.1-mini", system="s", user="u", on_delta=received.append
    )

    assert received == ["# Acme", "\n\nRockets."]
    assert text == "# Acme\n\nRockets."
    assert (usage.model, usage.prompt_tokens, usage.completion_tokens) == (SERVED_MODEL, 900, 40)


async def test_gemini_provider_sends_requests_to_googles_endpoint_with_the_key():
    from week1_brochure.config import PROVIDERS
    from week1_brochure.llm import client_for

    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=completion('{"links": []}'))

    http = openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    client = client_for(PROVIDERS["gemini"], "gemini-test-key", http_client=http, max_retries=0)

    await OpenAILLM(client).parse(
        model="gemini-3.5-flash-lite", system="s", user="u", schema=LinkSelection
    )

    assert str(requests[0].url) == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )
    assert requests[0].headers["authorization"] == "Bearer gemini-test-key"


async def test_streaming_without_a_usage_chunk_reports_usage_as_unknown():
    """Gemini's compatibility layer doesn't document include_usage; don't invent zeros."""
    data = {
        "id": "c",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "gemini-3.8-flash",
        "choices": [{"index": 0, "delta": {"content": "Hi"}, "finish_reason": "stop"}],
    }
    body = f"data: {json.dumps(data)}\n\ndata: [DONE]\n\n"
    response = httpx2.Response(
        200, content=body.encode(), headers={"content-type": "text/event-stream"}
    )

    text, usage = await llm_returning(response).complete(
        model="gemini-3.8-flash", system="s", user="u", on_delta=lambda _: None
    )

    assert text == "Hi"
    assert (usage.prompt_tokens, usage.completion_tokens) == (None, None)


def test_provider_clients_retry_long_enough_for_capacity_spikes():
    from week1_brochure.config import PROVIDERS
    from week1_brochure.llm import DEFAULT_MAX_RETRIES, client_for

    assert client_for(PROVIDERS["gemini"], "k").max_retries == DEFAULT_MAX_RETRIES
    assert client_for(PROVIDERS["gemini"], "k", max_retries=0).max_retries == 0


async def test_api_errors_name_the_model_that_failed(caplog):
    error = {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}}
    with pytest.raises(openai.InternalServerError):
        await parse_links(llm_returning(httpx2.Response(503, json=error)))
    assert "Request to gpt-5-nano failed (link selection)" in caplog.text
