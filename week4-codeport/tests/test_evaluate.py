"""These compile and run real C++ (CI's Ubuntu runner has g++). They skip if no compiler."""

import pytest

from week4_codeport.benchmarks import BENCHMARKS
from week4_codeport.evaluate import (
    Evaluation,
    evaluate_cpp,
    median_seconds,
    normalise_output,
    reference_outputs,
)
from week4_codeport.report import leaderboard
from week4_codeport.runner import RunResult, compile_cpp, run

PI, MAXSUB = BENCHMARKS["pi"], BENCHMARKS["max_subarray"]


@pytest.fixture(scope="module")
def expected():
    return {name: reference_outputs(b) for name, b in BENCHMARKS.items()}


def test_python_reference_produces_the_known_answers(expected):
    assert expected["pi"][0] == "Result: 3.142092403684"
    assert expected["max_subarray"][2] == "Total Maximum Subarray Sum (20 runs): 1210297272800"


@pytest.mark.parametrize(
    ("bench", "file"), [(PI, "pi_good.cpp"), (MAXSUB, "max_subarray_good.cpp")]
)
def test_a_correct_port_passes_every_input_and_is_timed(
    bench, file, expected, compiler, port_source
):
    result = evaluate_cpp(
        file,
        port_source(file),
        bench,
        expected[bench.name],
        compiler=compiler,
        runs=1,
        python_seconds=2.0,
    )

    assert result.status == "correct", result.cases
    assert result.seconds is not None and result.speedup > 1


def test_32_bit_overflow_passes_easy_inputs_but_fails_the_large_one(
    expected, compiler, port_source
):
    result = evaluate_cpp(
        "int32",
        port_source("max_subarray_int32.cpp"),
        MAXSUB,
        expected["max_subarray"],
        compiler=compiler,
        runs=1,
    )

    problems = [c.problem for c in result.cases]
    assert problems == [None, None, "output differs", None]
    assert result.status == "wrong output (1/4 inputs)"
    assert result.seconds is None  # wrong ports are not timed


def test_hard_coding_the_example_answer_is_caught(expected, compiler):
    cheat = '#include <cstdio>\nint main(){ std::puts("Result: 3.142092403684"); }\n'
    result = evaluate_cpp("cheat", cheat, PI, expected["pi"], compiler=compiler, runs=1)
    assert [c.problem for c in result.cases] == [
        None,
        "output differs",
        "output differs",
        "output differs",
    ]


def test_compile_errors_are_reported(expected, compiler):
    result = evaluate_cpp("broken", "int main( {", PI, expected["pi"], compiler=compiler)
    assert result.status == "does not compile"
    assert "error" in result.compile_errors.lower()


def test_an_endless_loop_is_stopped(tmp_path, compiler):
    built = compile_cpp(
        "int main(){ volatile long x = 0; for(;;) x++; }", tmp_path, compiler=compiler
    )
    outcome = run([str(built.binary)], cwd=tmp_path, timeout=1)
    assert outcome.timed_out and not outcome.ok


def test_median_ignores_one_slow_run_and_gives_up_on_failure(tmp_path):
    times = iter([0.5, 0.1, 0.2])

    def fake(*_a, **_k):
        return RunResult("", "", 0, next(times), False)

    assert median_seconds(["x"], cwd=tmp_path, runs=3, timeout=1, runner=fake) == 0.2

    def failing(*_a, **_k):
        return RunResult("", "boom", 1, 0.1, False)

    assert median_seconds(["x"], cwd=tmp_path, runs=3, timeout=1, runner=failing) is None


def test_output_comparison_ignores_trailing_whitespace_only():
    assert normalise_output("Result: 1  \r\n") == normalise_output("Result: 1")
    assert normalise_output("Result: 1.0") != normalise_output("Result: 1")


def test_leaderboard_ranks_correct_ports_by_speed_and_explains_failures():
    fast = Evaluation("fast", compiled=True, seconds=0.01, python_seconds=2.0)
    slow = Evaluation("slow", compiled=True, seconds=0.1, python_seconds=2.0)
    broken = Evaluation("broken", compiled=False, compile_errors="main.cpp:1: error: x")
    for e in (fast, slow):
        e.cases = [_ok_case()]

    md = leaderboard([slow, broken, fast], benchmark="pi", size="quick", python_seconds=2.0)

    rows = [line for line in md.splitlines() if line.startswith("| ") and "`" in line]
    assert rows[0].startswith("| 1 | `fast` | correct | 0.0100 s | 200x |")
    assert rows[1].startswith("| 2 | `slow`")
    assert rows[2].startswith("| — | `broken` | does not compile")
    assert "`broken`: compile error: `main.cpp:1: error: x`" in md


def _ok_case():
    from week4_codeport.evaluate import CaseResult

    return CaseResult(("1",), "a", "a", None)
