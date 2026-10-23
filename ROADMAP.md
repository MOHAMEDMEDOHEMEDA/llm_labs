# Roadmap

Plan for turning the LLM Engineering course into GitHub work that holds up in a Staff / Lead-level review, ending in an iOS capstone.

---

## 1. The honest framing

- **Course projects are a learning log, not CV projects.** Hiring managers in AI see the same course exercises often, and the course's own `community-contributions` folder holds many copies. They show you did the course; they don't show what you can design.
- **The capstone is the CV project.** It is the one thing listed under *Projects* on the CV, with its own pinned repo.
- **The learning repo still earns its place** if every project shows a decision the course didn't make for you. That's the "Beyond the course" column in the README.

### How it appears on the CV

```
PROJECTS
<Capstone name> — iOS app + LLM backend                         github.com/MOHAMEDMEDOHEMEDA/<capstone>
  One line: the problem, for whom.
  One line: architecture (SwiftUI · FastAPI · RAG/agents · on-device model) and one hard decision.
  One line: a measured result (eval score, latency, cost per request, test coverage).

TRAINING
LLM Engineering (Ed Donner, Udemy) — 8 projects rebuilt and extended   github.com/MOHAMEDMEDOHEMEDA/llm_labs
```

---

## 2. Repository setup

- **Two repos.** `llm-engineering-lab` (this one) and a separate capstone repo. Pin the capstone first, this one second.
- **Create a new repo; do not fork** `ed-donner/llm_engineering`. A fork shows "forked from" at the top, pulls in all the course content, and GitHub does not count commits made in a fork toward your contribution graph.
- **License compliance.** The course repo is MIT. Copying or adapting its files is allowed, provided the copyright and license notice travel with them. Keep a copy in `LICENSES/` and a header comment in each adapted file (for example, the course's `scraper.py`).
- **Secrets hygiene, set up on day one:**
  - `.env` in `.gitignore`; commit only `.env.example` with variable names.
  - `nbstripout` so notebook outputs (which can contain keys, scraped data, or long responses) never get committed.
  - `gitleaks` as a pre-commit hook. A leaked key on a public profile is a worse signal than no repo.
- **Tooling:** `uv` for environments, `ruff` for lint and format, `pytest`, and a GitHub Actions workflow that runs lint and tests on every push. A green CI badge is cheap credibility.

---

## 3. Definition of done for each week's project

A week's project counts as ✅ only when all of these are true:

- [ ] Code lives in `src/` as importable modules; the notebook is a walkthrough that imports them.
- [ ] At least one decision the course didn't make, documented in the project README.
- [ ] Tests that run **without** calling an API (mock the LLM client; use recorded fixtures for fetched pages).
- [ ] Errors handled at the boundaries: network, malformed model output, rate limits.
- [ ] Model names and limits in config, not hardcoded in functions.
- [ ] README with the four sections: taught / changed / limits / next.
- [ ] Rough cost per run noted.

Keep each week to a short timebox. The goal is to keep moving through the course; depth goes into the capstone.

---

## 4. Week 1 — Company brochure generator (concrete plan)

The course version works as a demo. These are the issues to fix, each one a line in the project README:

| Issue in the course code | Why it matters | Fix |
|---|---|---|
| `user_prompt[:5_000]` cuts after joining all pages | Later pages (often About or Careers) are silently dropped; the model never sees them | Token budget per source, measured with a tokenizer, trimmed per page |
| JSON mode with no schema; `links['links']` assumed | One drift in the model's output raises a `KeyError` and kills the run | Structured outputs with a Pydantic model; validate and retry once |
| One failing page fetch stops everything | Real sites time out, block bots, or return 404s | Fetch each page independently; skip and log failures; report which pages were used |
| Pages fetched one at a time | Slow on sites with many relevant links | Concurrent fetching (`asyncio` + `httpx`) with a limit and timeouts |
| `MODEL` defined, then `gpt-4.1-mini` hardcoded | Config drift; you can't tell which model produced what | Both models in config; record model and token usage per run |
| Key check only accepts `sk-proj-` keys | Valid keys of other formats are reported as problems | Check presence only; let the API report invalid keys |
| No relative-URL handling in code | Relying on the model to resolve `/about` is fragile | Resolve relative links with `urljoin` before the model sees them |
| No output beyond the notebook | Not usable outside Jupyter | CLI: `brochure <name> <url> --tone formal --out brochure.md` |

**Stretch, only if quick:** a small evaluation. Run five company sites and check each brochure against the source pages for unsupported claims. This is the habit that matters most in the capstone.

---

## 5. Weeks 2–8 — what to capture for the capstone

The exact projects depend on the current course version, so this lists the skill to come out with rather than the exercise. Fill in the README table as each week finishes.

| Week | Skill to come out with | Why the capstone needs it |
|---|---|---|
| 2 | Tool / function calling; streaming chat; multimodal input | The backend's API surface and the app's chat or streaming UI |
| 3 | Running open models; tokenizers; choosing a small model | Cheaper or on-device tasks; understanding token budgets |
| 4 | Comparing models on cost, latency, and quality for one task | Justifying the model choice in the capstone README with numbers |
| 5 | RAG: chunking, embeddings, retrieval quality | Answers grounded in the user's or app's own data |
| 6–7 | Fine-tuning (frontier, then QLoRA on an open model) | Optional in the capstone; at minimum, knowing when *not* to fine-tune |
| 8 | Agents and deployment | Multi-step workflows on the backend; putting the service online |

**Decision gate after Week 5:** pick the capstone idea. By then you know RAG and tools, which is enough to judge what's feasible.

---

## 6. Capstone — iOS app + LLM service

### Non-negotiable architecture rule

**No provider API keys in the iOS app.** Anything shipped in an app binary can be extracted. The app talks to your own backend; the backend holds the keys, enforces rate limits, and logs usage. This is exactly the kind of decision your security background lets you explain well in an interview.

```
SwiftUI app ──HTTPS──▶ FastAPI backend ──▶ LLM providers (OpenAI / Anthropic / open models)
   │                        │
   │                        ├─ RAG store (embeddings)
   │                        ├─ agent / tool orchestration
   │                        └─ eval + usage logging
   │
   └─ On-device model (Apple Foundation Models) for small, private, or offline tasks
```

The on-device split is the part that makes this capstone yours rather than a course clone. Apple's Foundation Models framework (iOS 26+) runs on Apple Intelligence–capable devices only and has a small context window (about 4K tokens), so it suits short tasks: classifying, summarizing one item, extracting fields. Long-document and multi-source work stays on the backend. Verify current device support and limits against Apple's documentation when you start; this changes with each OS release.

### Candidate ideas (decide at the Week 5 gate)

1. **App Review Intel** *(current recommendation)* — paste an App Store link; the backend pulls the app's metadata, public reviews, and the developer's site, then returns a structured brief: recurring complaints, bugs, feature requests, sentiment by app version, and a comparison with competitors. Uses the Week 1 pipeline, Week 2 tools, Week 5 RAG, and Week 8 agents. Fits a Lead Mobile / Lead AI story because the domain is mobile products.
   - **Data caveat:** Apple's public reviews RSS feed works for apps you don't own, but it's per country, paginated, capped at about 500 recent reviews, rate-limited, and a legacy endpoint that has behaved inconsistently. State this in the README and design around it (cache, multiple territories, graceful empty results).
2. **Job-hunt company brief** — company URL + job post + CV → company brief and a tailored pitch. Closest to the course and useful right now, but less distinctive.
3. **Something from your domain** — an assistant over a public dataset you know well (government services, healthcare information, parking). Strongest story if the data is public and you can evaluate it properly; avoid anything that touches your employer's private data.

### What makes the capstone CV-grade

- An **evaluation set** and a number in the README (e.g. "brief claims supported by source text: X% on 30 apps").
- **Cost and latency per request**, measured.
- **Tests on both sides:** Swift Testing for the app, pytest for the backend.
- A **short demo video or GIF** at the top of the README.
- An **architecture decision record** for the 2–3 hardest choices (on-device vs server, model choice, RAG vs fine-tuning).

---

## 7. Open questions for later

- Which capstone idea (decide after Week 5).
- Hosting for the backend (cheapest option that stays up for reviewers to try).
- Whether the iOS app ships to TestFlight or stays a demo build with a video.
