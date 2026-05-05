import sys
from collections.abc import Callable, Iterable
from typing import Any, TypeAlias

import pytest

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")
pytest.mark.skipif("PyPy" in sys.version, reason="CodSpeed doesn't support PyPy")

pytestmark = pytest.mark.benchmark


CasesMapType: TypeAlias = dict[Callable[..., Any], Iterable[Any]]
