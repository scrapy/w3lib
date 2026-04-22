from collections.abc import Callable, Iterable
from typing import Any, TypeAlias

import pytest

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

pytestmark = pytest.mark.benchmark


CasesMapType: TypeAlias = dict[Callable[..., Any], Iterable[Any]]
