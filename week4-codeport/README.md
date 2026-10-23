# Week 4 — Python to C++ porting benchmark

Asks several models to port a slow Python program to C++, then compiles every port, checks its output against Python's **exactly** on inputs the model never saw, and times only the ports that pass. The result is a leaderboard with the reason each failing port failed.

```bash
uv run python -m week4_codeport                                   # max_subarray, Gemini models
uv run python -m week4_codeport --benchmark pi --models gemini-3.8-flash,gemini-3.5-flash-lite
uv run python -m week4_codeport --provider ollama --models qwen2.5-coder
uv run python -m week4_codeport --cpp my_port.cpp                 # check your own C++, no model
uv run python -m week4_codeport --size full --save-code output/ports --out output/board.md
```

Needs a C++ compiler: on macOS `xcode-select --install`, on Ubuntu `sudo apt install g++`.

> **This runs code written by a model on your machine.** Each run has a timeout, CPU and file-size limits (plus a memory limit on Linux), its own temporary folder and a minimal environment. That is not a sandbox: the code can still read your files and use the network. Use a container or VM if that matters.

## Example output

From the hand-written ports in `tests/ports/` (no model involved), on this repo's Linux test machine:

```
| Rank | Port                     | Result                    | Time (median) | Speedup vs Python |
|------|--------------------------|---------------------------|---------------|-------------------|
| 1    | max_subarray_good.cpp    | correct                   | 0.0045 s      | 493x              |
| —    | max_subarray_int32.cpp   | wrong output (1/4 inputs) | —             | —                 |

- max_subarray_int32.cpp on `120 4294967295 -3 1000000000`: output differs.
  Expected `... 1210297272800`, got `... 42695592081`
```

The 32-bit port gives the right answer on the three ordinary inputs, including the course-style one, and fails only on the input with large values. Testing on more than the example input is what catches it.

## How it works

```
Python program ──▶ run on 4 check inputs ──▶ expected outputs
      │
      ▼
models port it (in parallel) ──▶ extract the ```cpp block ──▶ compile (-std=c++17 -O3)
                                                                  │
            run on the same 4 inputs, compare output exactly ◀───┘
                 │ all match                  │ any differ / crash / timeout
                 ▼                            ▼
       time it: median of N runs        listed with the first failing input
       measured from outside
```

| Module | Role |
|---|---|
| `benchmarks/` | The two Python programs from the course, changed to take their inputs from the command line, plus the check and timing inputs |
| `port.py` | The prompt, the model call, and extracting the C++ from the reply |
| `runner.py` | Compiling and running with limits; finding a compiler |
| `evaluate.py` | Exact output checks, timing, and the result for each port |
| `report.py` | The leaderboard |

## What the course taught

Week 4 compares models on a real task: porting Python to C++ (and Rust) for speed. The notebooks compile each model's code, print the run time the program reports, and compare speedups. On the harder benchmark, Ed's results list six of nine models as "FAIL", judged by reading the output.

## What I changed and why

| Course version | Problem | This version |
|---|---|---|
| Correctness judged by reading the output | Easy to miss a wrong digit; not repeatable | Output must match Python exactly on 4 inputs; the leaderboard shows the first mismatch |
| Tested on the one input that's also in the prompt | A port can hard-code the answer, or work only for small values | Inputs come from the command line, and 3 of the 4 check inputs are never shown to the model. The tests include a port that prints the example's answer, and one that overflows only on large values |
| The program prints its own run time | Generated code can report any number it likes | Programs print only their result; time is the median of several runs, measured from outside |
| Compiled with `-Ofast` | It allows reordering of floating-point maths. I measured `g++ -Ofast` changing the pi result from 3.141592678**590** to …**623** at 20M iterations, so a correct port fails an exact check | `-std=c++17 -O3` |
| Code taken from the reply with `.replace("```cpp", "")` | Breaks on prose, several blocks, or another tag | The tagged C++ block is extracted; falls back to the longest block |
| Generated code run directly in the notebook folder | It can overwrite files there or hang the notebook | Temporary folder, timeout, CPU, file-size and memory limits, minimal environment |
| One client per provider, models changed in code | Hard to re-run | `--provider` and `--models` flags; models ported in parallel; `--cpp` checks any file |

## Verification

- **18 tests** (`uv run pytest week4-codeport`). Most compile and run real C++ (CI's Ubuntu runner has g++; they skip if no compiler is found). Covered: the Python reference values, correct ports passing and being timed, the 32-bit overflow port, a hard-coded answer, compile errors, an endless loop being stopped, the timing median, code extraction, the prompt's requirements, the model call through the real SDK, the leaderboard order, and the CLI.
- **Checked by hand:** the hand-written pi port prints the same 12 digits as Python at every check input with `-O3` under both g++ and clang++. With `-Ofast`, g++ changed the result at 20M and 200M iterations; clang++ with `-march=native` changed the last digit at 200M.
- **Not yet done:** a live run with real models. That's the point of the project, so it's the first thing to do; paste the leaderboard into this README.

## Cost per run

One model call per model, roughly 400–550 tokens in (the prompt includes the Python source) and a few hundred to a few thousand out, more for models that reason first. Timing Python on the `full` size takes about half a minute; `quick` takes a few seconds.

## Limits

- **Two benchmarks**, both small numeric loops. They show speed and integer and float handling, not how models port real programs with I/O, classes or libraries.
- **Process start-up is included in the time.** For ports that finish in a few milliseconds, start-up is a large share, so speedups at the `quick` size are understated. Use `--size full` for numbers to quote.
- **Timings are machine-specific** and noisy; the median of 3 runs reduces but doesn't remove that.
- **Not a sandbox** (see the warning above). macOS doesn't enforce the memory limit.
- **Rust**, which the course also covers, isn't supported yet.

## What I'd do next

- Add a third benchmark with string processing and I/O, where ports fail in different ways.
- Repeat each model 3 times: a model that's correct once in three is worth knowing about.
- Feeds the capstone: the same "check on unseen inputs, measure from outside" discipline is how to choose the capstone's model with numbers rather than impressions.

---

Course: Ed Donner, *LLM Engineering* ([ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering), MIT). The two benchmark programs are adapted from the course's week 4 notebooks; each file names its source. See `LICENSES/` at the repo root.
