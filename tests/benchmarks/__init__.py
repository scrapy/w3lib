import sys
from collections.abc import Callable, Iterable
from typing import Any, TypeAlias

import pytest

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

BENCHMARK_MARKS = [
    pytest.mark.benchmark,
    pytest.mark.skipif("PyPy" in sys.version, reason="CodSpeed doesn't support PyPy"),
]

CasesMapType: TypeAlias = dict[Callable[..., Any], Iterable[Any]]
