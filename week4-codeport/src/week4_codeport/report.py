"""Leaderboard: correct ports first, fastest first; failures listed with the reason."""

from __future__ import annotations

from collections.abc import Sequence

from .evaluate import Evaluation


def _order(e: Evaluation) -> tuple[int, float]:
    if e.correct and e.seconds is not None:
        return (0, e.seconds)
    return (1 if e.compiled else 2, 0.0)


def leaderboard(
    evaluations: Sequence[Evaluation], *, benchmark: str, size: str, python_seconds: float | None
) -> str:
    lines = [
        f"## {benchmark} ({size} size)",
        "",
        f"Python: {python_seconds:.3f} s (median)" if python_seconds else "Python: not timed",
        "",
        "| Rank | Port | Result | Time (median) | Speedup vs Python |",
        "|---|---|---|---|---|",
    ]
    for rank, e in enumerate(sorted(evaluations, key=_order), start=1):
        timing = f"{e.seconds:.4f} s" if e.seconds is not None else "—"
        speedup = f"{e.speedup:,.0f}x" if e.speedup else "—"
        place = str(rank) if e.correct else "—"
        lines.append(f"| {place} | `{e.label}` | {e.status} | {timing} | {speedup} |")

    failures = [e for e in evaluations if not e.correct]
    if failures:
        lines += ["", "### Why ports failed", ""]
        for e in failures:
            if not e.compiled:
                first = e.compile_errors.splitlines()[0] if e.compile_errors else "no output"
                lines.append(f"- `{e.label}`: compile error: `{first}`")
                continue
            for case in e.cases:
                if case.problem:
                    lines.append(
                        f"- `{e.label}` on `{' '.join(case.args)}`: {case.problem}. "
                        f"Expected `{case.expected}`, got `{case.actual or '(nothing)'}`"
                    )
                    break
    return "\n".join(lines) + "\n"
