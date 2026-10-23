"""The Python programs to port, and the inputs used to check and time them.

Correctness is checked on several inputs, including ones the model is never shown, so a
port that hard-codes the answer for the example input fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).parent


@dataclass(frozen=True)
class Benchmark:
    name: str
    path: Path
    usage: str
    example_args: tuple[str, ...]  # shown to the model in the prompt
    check_args: tuple[tuple[str, ...], ...]  # small inputs; outputs must match Python exactly
    timing_args: dict[str, tuple[str, ...]]  # size -> input used for timing

    @property
    def source(self) -> str:
        return self.path.read_text(encoding="utf-8")


BENCHMARKS = {
    "pi": Benchmark(
        name="pi",
        path=_HERE / "pi_series.py",
        usage="ITERATIONS PARAM1 PARAM2",
        example_args=("200000000", "4", "1"),
        check_args=(("1000", "4", "1"), ("54321", "4", "1"), ("777", "3", "2"), ("1", "5", "1")),
        timing_args={"quick": ("20000000", "4", "1"), "full": ("200000000", "4", "1")},
    ),
    "max_subarray": Benchmark(
        name="max_subarray",
        path=_HERE / "max_subarray.py",
        usage="N INITIAL_SEED MIN_VAL MAX_VAL",
        example_args=("10000", "42", "-10", "10"),
        check_args=(
            ("200", "42", "-10", "10"),
            ("150", "7", "-50", "5"),  # mostly negative numbers
            ("120", "4294967295", "-3", "1000000000"),  # seed at 2**32 - 1, huge values
            ("1", "1", "-10", "-10"),
        ),
        timing_args={"quick": ("2000", "42", "-10", "10"), "full": ("10000", "42", "-10", "10")},
    ),
}
