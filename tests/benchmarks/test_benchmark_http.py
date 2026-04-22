from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, Any

import pytest

from w3lib.http import basic_auth_header, headers_dict_to_raw, headers_raw_to_dict

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-not-found]

    from tests.benchmarks import CasesMapType


BENCHMARK_CASES: CasesMapType = {
    basic_auth_header: [
        (("someuser", "somepass"), {}),
        (("someuser", "@<yu9>&o?Q"), {}),
        (("somæusèr", "sømepäss"), {"encoding": "utf8"}),
        (("somæusèr", "sømepäss"), {}),  # default encoding
    ],
    headers_raw_to_dict: [
        ((None,), {}),
        ((b"",), {}),
        (
            (
                b"Content-type: text/html\n\rAccept: gzip\n\r"
                b"Cache-Control: no-cache\n\rCache-Control: no-store\n\n",
            ),
            {},
        ),
    ],
    headers_dict_to_raw: [
        ((None,), {}),
        (({},), {}),
        (
            (
                OrderedDict(
                    [
                        (b"Content-type", b"text/html"),
                        (b"Accept", b"gzip"),
                    ]
                ),
            ),
            {},
        ),
        (
            (
                OrderedDict(
                    [
                        (b"Content-type", [b"text/html"]),
                        (b"Accept", [b"gzip"]),
                    ]
                ),
            ),
            {},
        ),
        (
            (
                OrderedDict(
                    [
                        (b"Content-type", (b"text/html",)),
                        (b"Accept", (b"gzip",)),
                    ]
                ),
            ),
            {},
        ),
        (
            (
                OrderedDict(
                    [
                        (b"Cookie", (b"val001", b"val002")),
                        (b"Accept", b"gzip"),
                    ]
                ),
            ),
            {},
        ),
        (
            (
                OrderedDict(
                    [
                        (b"Cookie", [b"val001", b"val002"]),
                        (b"Accept", b"gzip"),
                    ]
                ),
            ),
            {},
        ),
        (
            (
                OrderedDict(
                    [
                        (b"Content-type", 0),
                    ]
                ),
            ),
            {},
        ),
        (
            (
                OrderedDict(
                    [
                        (b"Content-type", 1),
                        (b"Accept", [b"gzip"]),
                    ]
                ),
            ),
            {},
        ),
    ],
}


@pytest.mark.parametrize("func", BENCHMARK_CASES)
def test_benchmark_http(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
) -> None:
    @benchmark
    def factory():
        for args, kwargs in BENCHMARK_CASES[func]:
            func(*args, **kwargs)
