"""Check a C++ port against the Python original, then time both.

A port passes only if its output matches Python's exactly on every check input. Only
then is it timed: the median of several runs, measured from outside the program.
"""

from __future__ import annotations

import statistics
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .benchmarks import Benchmark
from .runner import CompileResult, RunResult, compile_cpp, python_command, run


def normalise_output(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


@dataclass(frozen=True)
class CaseResult:
    args: tuple[str, ...]
    expected: str
    actual: str
    problem: str | None  # None means the output matched


@dataclass
class Evaluation:
    label: str  # model name, or the file that was checked
    compiled: bool = False
    compile_errors: str = ""
    cases: list[CaseResult] = field(default_factory=list)
    seconds: float | None = None  # median run time on the timing input
    python_seconds: float | None = None

    @property
    def correct(self) -> bool:
        return self.compiled and bool(self.cases) and all(c.problem is None for c in self.cases)

    @property
    def speedup(self) -> float | None:
        if self.seconds and self.python_seconds:
            return self.python_seconds / self.seconds
        return None

    @property
    def status(self) -> str:
        if not self.compiled:
            return "does not compile"
        failed = [c for c in self.cases if c.problem]
        if failed:
            return f"wrong output ({len(failed)}/{len(self.cases)} inputs)"
        return "correct"


Runner = Callable[..., RunResult]


def reference_outputs(
    benchmark: Benchmark, *, timeout: float = 60, runner: Runner = run
) -> list[str]:
    outputs = []
    for args in benchmark.check_args:
        result = runner(
            python_command(benchmark.path, args), cwd=benchmark.path.parent, timeout=timeout
        )
        if not result.ok:
            raise RuntimeError(f"The Python reference failed on {args}: {result.stderr}")
        outputs.append(normalise_output(result.stdout))
    return outputs


def check_binary(
    binary: Path,
    benchmark: Benchmark,
    expected: list[str],
    *,
    timeout: float = 10,
    runner: Runner = run,
) -> list[CaseResult]:
    cases = []
    for args, want in zip(benchmark.check_args, expected, strict=True):
        result = runner([str(binary), *args], cwd=binary.parent, timeout=timeout)
        got = normalise_output(result.stdout)
        if result.timed_out:
            problem = f"timed out after {timeout:.0f} s"
        elif result.returncode != 0:
            problem = f"exited with code {result.returncode}"
        elif got != want:
            problem = "output differs"
        else:
            problem = None
        cases.append(CaseResult(args, want, got, problem))
    return cases


def median_seconds(
    command: list[str], *, cwd: Path, runs: int, timeout: float, runner: Runner = run
) -> float | None:
    times = []
    for _ in range(runs):
        result = runner(command, cwd=cwd, timeout=timeout)
        if not result.ok:
            return None
        times.append(result.seconds)
    return statistics.median(times) if times else None


def evaluate_cpp(
    label: str,
    source: str,
    benchmark: Benchmark,
    expected: list[str],
    *,
    compiler: str,
    size: str = "quick",
    runs: int = 3,
    python_seconds: float | None = None,
    timeout: float = 60,
) -> Evaluation:
    evaluation = Evaluation(label, python_seconds=python_seconds)
    with tempfile.TemporaryDirectory(prefix="codeport-") as tmp:
        built: CompileResult = compile_cpp(source, Path(tmp), compiler=compiler)
        evaluation.compiled = built.ok
        evaluation.compile_errors = built.errors
        if not built.ok or built.binary is None:
            return evaluation
        evaluation.cases = check_binary(built.binary, benchmark, expected)
        if evaluation.correct:
            evaluation.seconds = median_seconds(
                [str(built.binary), *benchmark.timing_args[size]],
                cwd=Path(tmp),
                runs=runs,
                timeout=timeout,
            )
    return evaluation


def time_python(
    benchmark: Benchmark, *, size: str, runs: int, timeout: float = 600
) -> float | None:
    return median_seconds(
        python_command(benchmark.path, benchmark.timing_args[size]),
        cwd=benchmark.path.parent,
        runs=runs,
        timeout=timeout,
    )
