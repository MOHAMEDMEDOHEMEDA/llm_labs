# Week 2 — FlightAI support assistant

A customer support chat for a made-up airline. The model answers fare questions and starts bookings by calling tools backed by SQLite. A booking only becomes real when a person presses **Confirm booking** in the app.

```bash
uv run python -m week2_flightai               # Gemini by default; opens http://127.0.0.1:7860
uv run python -m week2_flightai --provider ollama -v   # a local model, logging each tool call
```

Try: *"How much is a return to Tokyo?"*, *"Do you fly to Rome?"*, *"Book Paris for Sara Ali."*

## How it works

```
user message ──▶ model (with 3 tools) ──▶ tool calls? ──yes──▶ validate args ──▶ run tool ──┐
                     ▲                         │ no                (Pydantic)     (SQLite)   │
                     └──────── tool results ───┼──────────────────────────────────────────────┘
                                               ▼              at most 4 rounds, then tools off
                                          answer shown
pending booking ──▶ "Confirm booking" button (plain code, not the model) ──▶ confirmed
```

| Module | Role |
|---|---|
| `store.py` | Fares and bookings in SQLite: parameterised queries, pending → confirmed / cancelled |
| `tools.py` | Tools defined once as Pydantic models; the JSON schema and the argument check come from the same class |
| `assistant.py` | The bounded tool loop, and an adapter for any OpenAI-compatible API |
| `app.py` | Gradio UI: chat, pending bookings, Confirm and Cancel buttons |
| `config.py` | Provider, model, system prompt |
| `labkit/providers.py` (shared) | Gemini, OpenAI, Hugging Face and Ollama endpoints |

## What the course taught

Week 2 builds chat UIs with Gradio and introduces tool calling: the model asks for `get_ticket_price`, the code runs it against SQLite and sends the result back, and a `while` loop repeats until the model stops asking. Day 5 adds image and speech generation, and the exercise suggests adding a booking tool.

## What I changed and why

| Course version | Problem | This version |
|---|---|---|
| Tool schema written by hand beside the function | The two drift apart; nothing checks the model's arguments | One Pydantic model per tool produces the schema and validates the arguments. Extra or missing fields are refused before any code runs |
| `while finish_reason == "tool_calls"` | A model that keeps calling tools loops forever, and costs money each time | At most 4 tool rounds, then one last call with tools switched off so the customer still gets an answer. Calls made after the limit are not executed |
| A tool error or unknown tool name raises | One bad call ends the conversation | Every failure becomes a JSON error the model can read and recover from. Unexpected exceptions are logged, and the model gets a generic message without internal details |
| The model's message is rebuilt by hand | Provider data on tool calls is lost | The assistant message is sent back exactly as received. Gemini, for example, can attach signatures to tool calls that must round-trip |
| Booking left as an exercise | A model with a "book" tool can book on a misunderstanding | The model can only create a **pending** booking. Confirming is a button handled by plain code, so a person approves every booking |
| Prices could be stated from memory | Wrong fares | The system prompt allows fares only from the tool; unknown cities return the list we serve |
| `gr.ChatInterface(type="messages")` | Gradio 6 removed the `type` parameter, and chat content can now be a list of parts | Custom `gr.Blocks` UI; history normalised to plain text messages |
| `launch()` with a hard-coded password | Credentials in source | Binds to `127.0.0.1` only; no share link, no password in code |

Image and speech generation from day 5 are left out on purpose: they cost per call and don't change the engineering of the assistant.

## Verification

- **27 offline tests** (`uv run pytest week2-flightai`), plus 4 for the shared provider module: SQLite behaviour including a SQL-injection attempt, schema generation, every tool-error path, the loop's limit and recovery, Gradio history parsing, the Confirm/Cancel logic, settings and the CLI.
- **SDK contract tests** run the real OpenAI SDK against a fake HTTP server through a full tool round trip. They check the tools sent, the tool reply, and that provider data on a tool call is echoed back unchanged.
- **UI smoke test** (manual, scripted model): launched the Gradio app and drove it through `gradio_client`. A booking request produced a pending row; Confirm turned it into `confirmed` in SQLite.
- **Not yet done:** a live run against Gemini. Function calling through Google's OpenAI-compatible endpoint is documented but labelled beta.

## Cost per run

Each customer message costs one model call, plus one more per tool round (usually one). With `gemini-3.8-flash`, a short conversation is a few thousand tokens. *First measured conversation: (fill in after a live run with `-v`.)*

## Limits

- **Small local models** (for example `llama3.2` on Ollama) call tools less reliably; the validation and error paths matter more there.
- **No streaming**: the answer appears when the tool loop finishes.
- **One shared database**: every browser tab sees the same pending bookings. A real app would tie bookings to a signed-in customer.
- **Prompt injection through tool results** is not an issue here, since the tools return only our own data; it would be for tools that fetch web pages.

## What I'd do next

- Record a few real conversations and turn them into regression tests for the prompt (does it ever claim a booking is confirmed?).
- Feeds the capstone: the "model proposes, person approves" pattern is how an iOS app should handle any action with consequences.

---

Course: Ed Donner, *LLM Engineering* ([ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering), MIT). The fares are the course's example data; the code is a reimplementation.
