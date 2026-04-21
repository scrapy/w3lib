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


def _header_case_long_headers():
    headers_dict = OrderedDict(
        [
            (b"X-Custom-Header", [b"a" * 1_000]),
            (b"X-Custom-Header-2", [b"b" * 1_000]),
        ]
    )
    raw = (
        b"X-Custom-Header: " + b"a" * 1_000 + b"\r\n"
        b"X-Custom-Header-2: " + b"b" * 1_000
    )  # fmt: off
    return headers_dict, raw


def _header_case_many_unique_headers():
    headers_dict = OrderedDict(
        [(f"Header-{i}".encode(), [f"value-{i}".encode()]) for i in range(100)]
    )
    raw = b"\r\n".join([f"Header-{i}: value-{i}".encode() for i in range(100)])
    return headers_dict, raw


def _header_case_many_repeated_headers():
    values = [f"id={i}".encode() for i in range(100)]
    headers_dict = OrderedDict([(b"Set-Cookie", values)])
    raw = b"\r\n".join([b"Set-Cookie: " + val for val in values])
    return headers_dict, raw


@pytest.mark.parametrize(
    ("headers_dict", "raw"),
    [
        _header_case_long_headers(),
        _header_case_many_unique_headers(),
        _header_case_many_repeated_headers(),
    ],
    ids=["long_headers", "many_unique_headers", "many_repeated_headers"],
)
class TestBenchmarkHttp:
    def test_bench_dict_to_raw(
        self,
        benchmark: BenchmarkFixture,
        headers_dict: OrderedDict[bytes, list[bytes]],
        raw: bytes,
    ) -> None:
        @benchmark
        def factory():
            assert headers_dict_to_raw(headers_dict) == raw

    def test_bench_raw_to_dict(
        self,
        benchmark: BenchmarkFixture,
        headers_dict: OrderedDict[bytes, list[bytes]],
        raw: bytes,
    ) -> None:
        @benchmark
        def factory():
            assert headers_raw_to_dict(raw) == headers_dict


@pytest.mark.parametrize("func", BENCHMARK_CASES)
def test_benchmark_url_general(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
) -> None:
    @benchmark
    def factory():
        for args, kwargs in BENCHMARK_CASES[func]:
            func(*args, **kwargs)
