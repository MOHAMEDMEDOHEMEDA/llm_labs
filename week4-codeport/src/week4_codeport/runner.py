"""Compile and run code written by a model, with limits.

This is not a sandbox. Each run gets its own temporary folder, a minimal environment, a
wall-clock timeout and (on Linux and macOS) CPU-time, file-size and, on Linux, memory
limits. Generated code can still read your files and use the network. Run it in a
container or a VM if that matters to you.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FLAGS = ("-std=c++17", "-O3")  # not -Ofast: it lets the compiler reorder float maths,
# which can change the last printed digits and make a correct port look wrong.


@dataclass(frozen=True)
class RunResult:
    stdout: str
    stderr: str
    returncode: int | None
    seconds: float
    timed_out: bool

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0


@dataclass(frozen=True)
class CompileResult:
    ok: bool
    binary: Path | None
    errors: str


def find_compiler(env: dict[str, str] | None = None) -> str | None:
    env = os.environ if env is None else env
    for candidate in (env.get("CXX"), "clang++", "g++"):
        if candidate and shutil.which(candidate):
            return candidate
    return None


def _limits(cpu_seconds: int, memory_mb: int):
    if sys.platform == "win32":
        return None

    def apply() -> None:  # runs in the child just before exec
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 2**20, 10 * 2**20))  # 10 MB files
        if sys.platform.startswith("linux"):  # macOS doesn't enforce RLIMIT_AS
            limit = memory_mb * 2**20
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

    return apply


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
    memory_mb: int = 2048,
) -> RunResult:
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "C", "LC_ALL": "C"}
    start = time.perf_counter()
    try:
        done = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=_limits(int(timeout) + 1, memory_mb),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return RunResult(out, "", None, time.perf_counter() - start, True)
    return RunResult(done.stdout, done.stderr, done.returncode, time.perf_counter() - start, False)


def compile_cpp(
    source: str,
    workdir: Path,
    *,
    compiler: str,
    flags: tuple[str, ...] = DEFAULT_FLAGS,
    timeout: float = 120,
) -> CompileResult:
    src = workdir / "main.cpp"
    binary = workdir / "main"
    src.write_text(source, encoding="utf-8")
    result = run(
        [compiler, *flags, str(src), "-o", str(binary)],
        cwd=workdir,
        timeout=timeout,
        memory_mb=4096,
    )
    if result.timed_out:
        return CompileResult(False, None, f"compiler timed out after {timeout:.0f} s")
    if result.returncode != 0:
        return CompileResult(False, None, _tail(result.stderr))
    return CompileResult(True, binary, "")


def python_command(script: Path, args: tuple[str, ...]) -> list[str]:
    return [sys.executable, "-I", str(script), *args]  # -I: ignore the user's environment


def _tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])
