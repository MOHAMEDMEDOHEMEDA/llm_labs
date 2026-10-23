import json

import httpx2
import openai

from labkit.providers import PROVIDERS, client_for
from week4_codeport.benchmarks import BENCHMARKS
from week4_codeport.port import extract_cpp, port, user_prompt


def test_extracts_the_cpp_block_from_a_chatty_reply():
    reply = "Here you go!\n```cpp\nint main() { return 0; }\n```\nCompile with -O3."
    assert extract_cpp(reply) == "int main() { return 0; }\n"


def test_prefers_tagged_cpp_over_other_blocks():
    reply = "```bash\ng++ main.cpp\n```\n```c++\n#include <cstdio>\nint main(){}\n```"
    assert extract_cpp(reply).startswith("#include <cstdio>")


def test_falls_back_to_an_untagged_block_then_the_whole_reply():
    assert extract_cpp("```\nint main(){}\n```") == "int main(){}\n"
    assert extract_cpp("int main(){}") == "int main(){}\n"


def test_prompt_demands_identical_output_and_command_line_inputs():
    prompt = user_prompt(BENCHMARKS["max_subarray"], "clang++")
    assert "exactly the same output" in prompt
    assert "inputs you have not seen" in prompt
    assert "N INITIAL_SEED MIN_VAL MAX_VAL" in prompt
    assert "clang++ -std=c++17 -O3 main.cpp -o main" in prompt
    assert "def total_max_subarray_sum" in prompt  # the real source is included


async def test_port_calls_the_model_and_returns_the_code():
    sent: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "gemini-3.8-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "```cpp\nint main(){return 0;}\n```",
                        },
                    }
                ],
                "usage": {"prompt_tokens": 700, "completion_tokens": 300, "total_tokens": 1000},
            },
        )

    http = openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    client = client_for(PROVIDERS["gemini"], "k", http_client=http, max_retries=0)

    result = await port(client, "gemini-3.8-flash", BENCHMARKS["pi"], "g++")

    assert result.code == "int main(){return 0;}\n"
    assert (result.prompt_tokens, result.completion_tokens) == (700, 300)
    assert sent[0]["model"] == "gemini-3.8-flash"
    assert "ITERATIONS PARAM1 PARAM2" in sent[0]["messages"][1]["content"]
