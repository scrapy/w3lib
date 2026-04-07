from collections.abc import Callable, Iterable
from typing import Any, TypeAlias

import pytest

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

pytestmark = pytest.mark.benchmark


CasesMapType: TypeAlias = dict[Callable[..., Any], Iterable[Any]]


def unroll_cases(
    cases_map: CasesMapType,
) -> Iterable[tuple[Callable[..., Any], Any, Any]]:
    for func, cases in cases_map.items():
        for args, kwargs in cases:
            yield func, args, kwargs
