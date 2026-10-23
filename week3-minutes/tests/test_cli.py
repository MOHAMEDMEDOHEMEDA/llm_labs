import json

import httpx2
import openai

from labkit.providers import PROVIDERS, client_for
from week3_minutes.__main__ import connection_help, main
from week3_minutes.config import Settings
from week3_minutes.minutes import OpenAICompatibleLLM, usage_summary


def test_defaults_to_a_local_open_model():
    settings = Settings.from_env({})
    assert (settings.provider, settings.model) == ("ollama", "llama3.2")
    assert Settings.from_env({}, provider="huggingface").model == "meta-llama/Llama-3.1-8B-Instruct"


def test_ollama_needs_no_key_but_huggingface_does(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    (tmp_path / "t.txt").write_text("Nadia: hello")
    assert main([str(tmp_path / "t.txt"), "--provider", "huggingface"]) == 2
    assert "HF_TOKEN" in capsys.readouterr().err


def test_missing_transcript_is_reported(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["nope.txt"]) == 2
    assert "No such file: nope.txt" in capsys.readouterr().err


def test_connection_help_tells_you_how_to_start_ollama():
    message = connection_help(PROVIDERS["ollama"])
    assert "ollama pull llama3.2" in message and "--provider huggingface" in message


async def test_adapter_sends_plain_chat_and_records_usage():
    sent: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "llama3.2",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"summary": "s"}'},
                    }
                ],
                "usage": {"prompt_tokens": 300, "completion_tokens": 40, "total_tokens": 340},
            },
        )

    http = openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    llm = OpenAICompatibleLLM(
        client_for(PROVIDERS["ollama"], "local", http_client=http, max_retries=0), "llama3.2"
    )

    assert await llm.chat([{"role": "user", "content": "hi"}]) == '{"summary": "s"}'
    assert sent[0]["temperature"] == 0.0 and "response_format" not in sent[0]
    assert usage_summary(llm) == "1 model calls, 300 prompt + 40 completion tokens"


def test_unreachable_ollama_becomes_a_connection_error(monkeypatch, tmp_path, capsys):
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    real_client_for = client_for

    def fake_client_for(provider, key, **kw):
        kw["http_client"] = openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(refuse))
        return real_client_for(provider, key, **{**kw, "max_retries": 0})

    import week3_minutes.__main__ as cli

    monkeypatch.setattr(cli, "client_for", fake_client_for)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "t.txt").write_text("Nadia: hello")
    assert cli.main([str(tmp_path / "t.txt")]) == 1
    assert "Couldn't reach Ollama" in capsys.readouterr().err
