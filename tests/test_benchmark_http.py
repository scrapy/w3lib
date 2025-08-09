from collections import OrderedDict

import pytest

from w3lib.http import headers_dict_to_raw, headers_raw_to_dict

pytest.importorskip("pytest_codspeed", reason="Benchmark tests require pytest-codspeed")

pytestmark = pytest.mark.benchmark


def _header_case_long_headers():
    dct = OrderedDict(
        [
            (b"X-Custom-Header", [b"a" * 1_000]),
            (b"X-Custom-Header-2", [b"b" * 1_000]),
        ]
    )
    raw = (
        b"X-Custom-Header: " + b"a" * 1_000 + b"\r\n"
        b"X-Custom-Header-2: " + b"b" * 1_000
    )  # fmt: off
    return "long_headers", dct, raw


def _header_case_many_unique_headers():
    dct = OrderedDict(
        [(f"Header-{i}".encode(), [f"value-{i}".encode()]) for i in range(100)]
    )
    raw = b"\r\n".join([f"Header-{i}: value-{i}".encode() for i in range(100)])
    return "many_unique_headers", dct, raw


def _header_case_many_repeated_headers():
    values = [f"id={i}".encode() for i in range(100)]
    dct = OrderedDict([(b"Set-Cookie", values)])
    raw = b"\r\n".join([b"Set-Cookie: " + val for val in values])
    return "many_repeated_headers", dct, raw


header_cases = [
    _header_case_long_headers(),
    _header_case_many_unique_headers(),
    _header_case_many_repeated_headers(),
]


@pytest.mark.parametrize(
    ("_id", "dct", "raw"),
    header_cases,
    ids=[case[0] for case in header_cases],
)
class TestBenchmarkHttp:
    def test_bench_dict_to_raw(self, benchmark, _id, dct, raw):  # noqa: PT019
        result = benchmark(lambda: headers_dict_to_raw(dct))
        assert result == raw

    def test_bench_raw_to_dict(self, benchmark, _id, dct, raw):  # noqa: PT019
        result = benchmark(lambda: headers_raw_to_dict(raw))
        assert result == dct
