from __future__ import annotations

from pathlib import Path

import pytest

from week4_codeport.runner import find_compiler

PORTS = Path(__file__).parent / "ports"

needs_compiler = pytest.mark.skipif(find_compiler() is None, reason="no C++ compiler installed")


@pytest.fixture
def port_source():
    def read(name: str) -> str:
        return (PORTS / name).read_text(encoding="utf-8")

    return read


@pytest.fixture
def compiler() -> str:
    found = find_compiler()
    if found is None:
        pytest.skip("no C++ compiler installed")
    return found
