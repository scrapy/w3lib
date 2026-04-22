import sys
from collections.abc import Callable, Iterable
from typing import Any, TypeAlias

import pytest

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

pytestmark = pytest.mark.benchmark


CasesMapType: TypeAlias = dict[Callable[..., Any], Iterable[Any]]

PYTHON_IMPL = (
    pytest.param(
        "CPython",
        marks=pytest.mark.skipif(
            sys.implementation.name != "cpython",
            reason="Not current python implementation",
        ),
    ),
    pytest.param(
        "PyPy",
        marks=pytest.mark.skipif(
            sys.implementation.name != "pypy",
            reason="Not current python implementation",
        ),
    ),
)
