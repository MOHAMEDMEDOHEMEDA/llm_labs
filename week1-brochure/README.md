# Week 1 — Company brochure generator

Give it a company name and website; it reads the relevant pages and writes a short brochure for prospective customers, investors and recruits.

```bash
uv run python -m week1_brochure "Hugging Face" https://huggingface.co --out output/hf.md
uv run python -m week1_brochure "Hugging Face" https://huggingface.co --tone humorous
uv run python -m week1_brochure "Hugging Face" https://huggingface.co --provider openai
```

The brochure streams to stdout; a run report (pages used, pages skipped, tokens per model call) goes to stderr.

## Providers

| Provider | Key (in `.env`) | Link selection | Writer |
|---|---|---|---|
| `gemini` (default) | `GEMINI_API_KEY`, or `GOOGLE_API_KEY` as in the course | `gemini-3.5-flash-lite` | `gemini-3.8-flash` |
| `openai` | `OPENAI_API_KEY` | `gpt-5-nano` | `gpt-4.1-mini` |

Gemini is called through Google's [OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai), so both providers share one adapter: the provider only changes the base URL, the key, and the default models. Override models with `BROCHURE_LINK_MODEL` / `BROCHURE_WRITER_MODEL`. Model names change often; the defaults follow Google's [models page](https://ai.google.dev/gemini-api/docs/models) as of October 2026.

## How it works

```
landing page ──▶ filter links in code ──▶ small model picks pages ──▶ fetch them concurrently
                 (same site, no legal/      (Structured Outputs,        (robots.txt, timeouts,
                  login/file links)          URLs checked against        failures recorded,
                                             the offered list)           not fatal)
                                                                              │
              brochure ◀── writer model (grounded prompt) ◀── per-page token budget
```

| Module | Role |
|---|---|
| `labkit/fetch.py` (shared) | Async fetching: robots.txt, size cap, redirects, typed `Page` |
| `links.py` | Deterministic link filtering before any model call |
| `selection.py` | Model picks pages; invented URLs dropped; one retry, then fall back |
| `budget.py` | Splits the token budget across pages so none is silently dropped |
| `pipeline.py` | Orchestration with injected fetcher, LLM and tokenizer |
| `llm.py` | One adapter for any OpenAI-compatible endpoint (Gemini, OpenAI); everything else is testable offline |
| `config.py` | Settings and the provider registry (base URL, key variables, default models) |

## What the course taught

A two-call pipeline. A small model reads the landing page's links and returns the relevant ones as JSON; a second model writes a brochure from the fetched pages, optionally streamed. It's the first example of chaining model calls, with one-shot prompting and JSON mode.

## What I changed and why

| Course version | Problem | This version |
|---|---|---|
| `user_prompt[:5_000]` after joining all pages | Later pages (often About or Careers) silently vanish | Each page gets a share of a token budget (water-filling); truncated pages are marked, and the report shows what was kept |
| JSON mode, no schema, `links['links']` assumed | One drift in the output crashes the run | Structured Outputs with a Pydantic schema and an enum for page type; unusable answers retried once, then the run continues from the landing page |
| Model trusted to return real URLs | It can invent or alter URLs | Only URLs that were in the offered list are kept, in their original spelling |
| Model asked to resolve relative links and skip legal pages | Fragile and costs tokens | Done in code with `urljoin` and filters; the model only makes the judgement call |
| Pages fetched one at a time; any failure stops everything | Slow, and real sites time out or 404 | Concurrent fetching with a limit; failures recorded and reported, not fatal. Unexpected exceptions are still raised, so bugs aren't hidden |
| Prompt says nothing about accuracy | Brochures can contain invented facts | Writer is told to use only facts in the pages and to treat page text as data, not instructions (scraped pages are untrusted input) |
| `MODEL` defined, then another model hardcoded | You can't tell which model produced what | Both models in `Settings`, overridable by env; the report records the model that actually served each call |
| One provider, wired into every call | Switching providers means editing code | Provider registry: Gemini or OpenAI by flag or env, same pipeline and adapter |
| Key check only accepts `sk-proj-` keys | Valid keys reported as problems | Checks presence only; the API reports invalid keys |
| Browser-imitating User-Agent, no robots.txt | Impolite scraping | Honest User-Agent; robots.txt respected per RFC 9309 |
| Notebook only | Not usable outside Jupyter, not testable | CLI plus importable package; notebook is a walkthrough |

## Verification

- **48 offline tests** (`uv run pytest`), no network or API key needed: link filtering, budget invariants (including a regression test for the course's truncation bug), selection retry and fallback, concurrent fetching within the limit, robots.txt handling, and the CLI's error paths.
- **SDK contract tests** run the real OpenAI SDK against a fake HTTP layer. They check the request asks for a strict JSON schema, that the Gemini provider sends requests to Google's endpoint with your key, and that refusals, cut-off answers and schema violations become `LLMOutputError`, while API errors such as a bad key are not disguised.
- **Live fetch** of a real site checked manually (robots.txt allowed, login/register links filtered out).
- **Live run** on Gemini (Hugging Face): link selection returned valid structured output through Google's compatibility endpoint, and both calls reported token usage.

## Cost per run

Two model calls per run: one for link selection, one for writing. The run report prints the prompt and completion tokens of each. Multiply by your models' current prices (they change; check the provider's pricing page rather than trusting a number in a README).

With Gemini, a streamed writer call may report no token usage: Google doesn't document `stream_options` on its compatibility endpoint. The report then says so instead of showing zeros; use `--no-stream` for a run where you need the numbers.

**First measured run** (Hugging Face, October 2026, `--no-stream`):

| Call | Model | Prompt tokens | Completion tokens | Paid-tier cost |
|---|---|---|---|---|
| Link selection | `gemini-3.5-flash-lite` | 1,023 | 166 | $0.0007 |
| Writer | `gemini-3.8-flash` | 7,108 | 526 | $0.0073 |
| **Total** | | | | **≈ $0.008** |

Prices from Google's [pricing page](https://ai.google.dev/gemini-api/docs/pricing) as of October 2026: Flash-Lite $0.30 / $2.50 and Flash $0.75 / $3.75 per 1M input / output tokens. Flash's price doubles on 1 January 2027, which would make this run about $0.015. Both models also have a free tier. Output prices include thinking tokens; I haven't confirmed that the compatibility endpoint counts those in `completion_tokens`, so treat the figure as a lower bound.

## Limits

- **JavaScript-rendered pages** return little or no text, because there's no headless browser. On the first live run the Workable careers page came back empty, so the brochure has no careers section. Empty pages are now reported as skipped rather than sent to the writer.
- **Honest User-Agent and robots.txt** mean some sites refuse; the run then reports why instead of failing silently.
- **Token budgeting** uses OpenAI's `o200k_base` encoding: exact for OpenAI models, an estimate for Gemini. Fine for splitting the budget; the billed numbers come from the run report.
- **Gemini through the compatibility layer**, which Google still labels beta. A native `google-genai` adapter would be the fix if a feature is missing; the `LLM` interface is where it would plug in.
- **No factual check of the output.** The prompt asks for grounded facts, but nothing verifies the brochure against the pages yet.
- **Usage of a failed selection attempt** isn't recorded in the report.
- The first run downloads tiktoken's encoding file; offline machines need it cached.

## What I'd do next

- **Grounding eval** (the ROADMAP stretch goal): for 5–10 companies, extract each claim in the brochure and check it against the source pages. Report the share supported. This is the habit the capstone needs most.
- Cache fetched pages on disk so repeated runs don't re-fetch.
- Feeds the capstone: the fetch → select → budget → write pipeline is the core of the App Review Intel idea.

---

Course: Ed Donner, *LLM Engineering* ([ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering), MIT). This project reimplements the Week 1 Day 5 exercise; no course code is copied. See `LICENSES/` at the repo root.
