from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypeAlias

import pytest

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

BENCHMARK_MARKS = [pytest.mark.benchmark]

CasesMapType: TypeAlias = dict[Callable[..., Any], Iterable[Any]]

# Real pages, one per way a document can shape the cost of a <base> lookup. In
# a sample of 246 pages from 96 popular sites (September 2026), 235 had no
# <base> at all, 3 had a <base> without href, and 1 had a <base href> in the
# head, so the no-base page is the representative workload and the others are
# the edge cases worth watching.
PAGES = {
    path.stem: path.read_bytes()
    for path in sorted((Path(__file__).parent / "pages").glob("*.html"))
}
