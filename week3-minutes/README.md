# Week 3 — Meeting minutes with open models

Turns a meeting transcript (or an audio file) into minutes: summary, attendees, decisions and action items with owners. It runs on open models, locally through Ollama or hosted through Hugging Face, and every decision and action item must quote the transcript. Anything whose quote or owner can't be found goes under **Needs checking** instead of being presented as fact.

```bash
ollama pull llama3.2                                    # once; https://ollama.com
uv run python -m week3_minutes week3-minutes/samples/product-sync.txt
uv run python -m week3_minutes notes.txt --provider huggingface --out output/minutes.md
uv run --with "transformers[torch]" python -m week3_minutes --audio meeting.mp3
```

On a GPU, [`colab.ipynb`](colab.ipynb) runs Whisper on Colab and sends the transcript to an open model on Hugging Face, as the course does.

## How it works

```
transcript ──▶ split into parts ──▶ open model: JSON notes per part ──▶ parse + validate
               (~1,500 tokens,                                            │ invalid?
                2 lines overlap)          ◀── "that reply could not be used: <error>" (up to 2×)
                                                                          ▼
                       check every quote and owner against the transcript ──▶ merge parts
                                  │ not found                                   │
                                  ▼                                             ▼
                           "Needs checking"                          minutes (Markdown)
```

| Module | Role |
|---|---|
| `transcript.py` | Load and split long transcripts on line boundaries, with overlap |
| `minutes.py` | Per-part extraction with repair retries, merging, Markdown output |
| `grounding.py` | Checks quotes and owners against the transcript |
| `models.py` | The JSON shape the model must return (Pydantic) |
| `prompts.py` | Short, explicit prompts written for small models |
| `transcribe.py` | Optional local Whisper via Hugging Face `transformers` |
| `labkit/jsonparse.py` (shared) | Finds the JSON object in a reply wrapped in prose or code fences |

## What the course taught

Week 3 moves to open-source models on Google Colab: Hugging Face pipelines, tokenizers, and loading models such as Llama with 4-bit quantisation on a T4 GPU. The week's project transcribes meeting audio with Whisper and asks Llama to write minutes in Markdown.

## What I changed and why

| Course version | Problem | This version |
|---|---|---|
| Minutes returned as free Markdown | Nothing can be checked or reused | The model returns JSON in a fixed shape, validated with Pydantic, then rendered |
| Small open models break JSON often, and most servers can't enforce a schema | One bad reply loses the meeting | The JSON is found even inside prose or code fences. If it's invalid, the model sees the exact error and tries again, up to twice. A part that never parses is reported, not fatal |
| Whole transcript in one prompt | Long meetings overflow an 8B model's context | Split on speaker lines with two lines of overlap; duplicates from the overlap are merged |
| Decisions and owners are taken on trust | Small models invent owners, dates and decisions | Every item must quote the transcript. Quotes are checked word for word (ignoring case and punctuation), and owners must be named in it. Failures go under **Needs checking** |
| "Ideas" and "decisions" mixed | Minutes overstate what was agreed | The prompt separates them; the sample transcript includes a parked idea to test this |
| Runs only in Colab with a GPU | Hard to iterate on a laptop | One OpenAI-compatible adapter covers Ollama (local), the Hugging Face router (hosted), Gemini and OpenAI. Audio is optional, so the core needs no PyTorch |

## Verification

- **34 offline tests** (`uv run pytest week3-minutes`), plus 8 for the shared JSON parser: splitting and overlap, quote and owner checks (paraphrases, invented surnames, curly quotes), repair retries with the error shown to the model, failed parts, merging across parts, Markdown output, the CLI's errors including Ollama not running, and the real SDK request (`temperature` 0, no `response_format`).
- **Not yet done:** a live run against Ollama or Hugging Face, and the Colab notebook end to end. Both are what the next session should do; record which items land in Needs checking.

## Cost per run

- **Ollama:** free, on your machine. `llama3.2` (3B) needs about 2 GB of memory.
- **Hugging Face router:** billed per token by the provider that serves the model; the sample transcript is about 600 tokens in, plus the reply. The CLI prints the token count from the server's report.

## Limits

- **Speaker names**: Whisper produces text without speakers, so owners are often missing from audio transcripts and land in Needs checking. Speaker diarisation would fix this.
- **Exact quotes only**: a model that paraphrases its evidence gets flagged even when the item is right. That errs on the side of caution.
- **The owner check proves a name appears, not that the person agreed** to the task.
- **Token counts are estimates** (4 characters per token), since each open model has its own tokenizer.
- **Llama 3.1 on Hugging Face is gated**: accept the licence on its page first, or set `MINUTES_MODEL`.

## What I'd do next

- Run the same transcript through two or three open models and compare how many items each gets into Needs checking: a cheap first evaluation.
- Feeds the capstone: "every claim must quote the source" is the core check for summarising App Store reviews.

---

Course: Ed Donner, *LLM Engineering* ([ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering), MIT). The sample transcript is invented for this repo.
