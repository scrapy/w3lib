from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

import pytest

from w3lib.http import headers_dict_to_raw, headers_raw_to_dict

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-not-found]

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

pytestmark = pytest.mark.benchmark


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
