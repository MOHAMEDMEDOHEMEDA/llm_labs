# LLM Engineering Lab

[![CI](https://github.com/MOHAMEDMEDOHEMEDA/llm_labs/actions/workflows/ci.yml/badge.svg)](https://github.com/MOHAMEDMEDOHEMEDA/llm_labs/actions/workflows/ci.yml)

My work through Ed Donner's **LLM Engineering** course, rebuilt as maintainable Python and extended beyond the course material. Each project lists what the course taught, what I changed, and where it still falls short.

This repo is the learning track. The capstone, an **iOS app backed by an LLM service**, will live in its own repository when development begins.

> **Author:** Mohamed Magdy — iOS Developer | Swift, SwiftUI, Flutter, React Native, moving into applied AI.
>
> GitHub: [@MOHAMEDMEDOHEMEDA](https://github.com/MOHAMEDMEDOHEMEDA)
---

## Projects

| Week | Topic | Project | Beyond the course | Status |
|---|---|---|---|---|
| 1 | Frontier APIs, multi-call pipelines | [Company brochure generator](week1-brochure/) | Gemini or OpenAI behind one adapter, schema-validated outputs, URL hallucination guard, per-page token budget, concurrent fetching with failure isolation, robots.txt, CLI, 48 offline tests; ≈ $0.008 per run | ✅ Done |
| 2 | Chat UIs, tools / function calling, multimodal | [FlightAI support assistant](week2-flightai/) | Tool schemas and argument checks from one Pydantic model, bounded tool loop, errors returned to the model, human confirmation for bookings, Gradio 6 UI, 27 offline tests | 🟨 Built; live run pending |
| 3 | Open-source models (Hugging Face) | — | — | ⬜ Planned |
| 4 | Model selection, code generation, evaluation | — | — | ⬜ Planned |
| 5 | Retrieval-augmented generation (RAG) | — | — | ⬜ Planned |
| 6 | Fine-tuning a frontier model | — | — | ⬜ Planned |
| 7 | QLoRA fine-tuning an open model | — | — | ⬜ Planned |
| 8 | Agents and deployment | — | — | ⬜ Planned |

Status key: ⬜ planned · 🟨 in progress · ✅ done (has tests and a project README)

---

## Repository layout

```
llm_labs/
├── README.md
├── ROADMAP.md               # plan, rules, capstone direction
├── pyproject.toml / uv.lock
├── .env.example             # variable names only, never real keys
├── .pre-commit-config.yaml  # gitleaks, nbstripout, ruff
├── .github/workflows/ci.yml # lint + tests on every push; no secrets needed
├── LICENSE                  # MIT, my code
├── LICENSES/                # notices for adapted third-party material
├── labkit/                  # code shared across weeks (fetching, model providers), with tests
├── week1-brochure/
│   ├── README.md            # taught / changed / limits / next
│   ├── src/week1_brochure/
│   ├── tests/
│   └── notebook.ipynb       # walkthrough, committed with outputs stripped
├── week2-flightai/          # same shape for every week
└── ...
```

## Running a project

```bash
git clone https://github.com/MOHAMEDMEDOHEMEDA/llm_labs.git
cd llm_labs
uv sync                      # creates .venv with runtime and dev dependencies
uv run pre-commit install    # secret scanning + notebook stripping on every commit
cp .env.example .env         # then add your Gemini (or OpenAI) key
uv run pytest                # offline; no API key needed
uv run python -m week1_brochure "Hugging Face" https://huggingface.co
uv run python -m week2_flightai           # opens the FlightAI chat in your browser
```

API calls cost money. Each project README states which models it calls and roughly what one run costs.

## Conventions

Every project README answers four questions:

1. **What the course taught** — one paragraph.
2. **What I changed and why** — the engineering decisions, not a feature list.
3. **Limits** — what breaks, what was not tested, what the data does not cover.
4. **What I'd do next** — and whether it feeds the capstone.

## Attribution and license

The course material is © Edward Donner and published under the MIT License in [ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering). Files adapted from the course keep a header comment naming the original file, and the course's MIT notice is reproduced in `LICENSES/llm_engineering-MIT.txt`.

My own code in this repository is released under the MIT License (see `LICENSE`).
