from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.benchmarks import BENCHMARK_MARKS, CasesMapType
from w3lib.encoding import (
    html_body_declared_encoding,
    html_encoding,
    html_to_unicode,
    http_content_type_encoding,
    read_bom,
    resolve_encoding,
    to_unicode,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-not-found]


pytestmark = BENCHMARK_MARKS

BENCHMARK_CASES: CasesMapType = {
    read_bom: [
        ((b"\xfe\xff\x6c\x34",), {}),
        ((b"\xff\xfe\x34\x6c",), {}),
        ((b"\x00\x00\xfe\xff\x00\x00\x6c\x34",), {}),
        ((b"\xff\xfe\x00\x00\x34\x6c\x00\x00",), {}),
        ((b"foo",), {}),
        ((b"",), {}),
    ],
    http_content_type_encoding: [
        (("Content-Type: text/html; charset=ISO-8859-4",), {}),
        (("something else",), {}),
    ],
    html_body_declared_encoding: [
        (
            (
                b"""<meta http-equiv="content-type" content="text/html;charset=UTF-8" />""",
            ),
            {},
        ),
        (
            (
                b"""\n<meta http-equiv="Content-Type"\ncontent="text/html; charset=utf-8">""",
            ),
            {},
        ),
        (
            (
                b"""<meta http-equiv="Content-Type" content="text/html" charset="utf-8">""",
            ),
            {},
        ),
        (
            (
                b"""<meta http-equiv=Content-Type content="text/html" charset='utf-8'>""",
            ),
            {},
        ),
        (
            (
                b"""<meta http-equiv="Content-Type" content\t=\n"text/html" charset\t="utf-8">""",
            ),
            {},
        ),
        (
            (
                b"""<meta content="text/html; charset=utf-8"\n http-equiv='Content-Type'>""",
            ),
            {},
        ),
        (
            (
                b""" bad html still supported < meta http-equiv='Content-Type'\n content="text/html; charset=utf-8">""",
            ),
            {},
        ),
        ((b"""<meta charset="utf-8">""",), {}),
        ((b"""<meta charset =\n"utf-8">""",), {}),
        ((b"""<?xml version="1.0" encoding="utf-8"?>""",), {}),
        ((b"something else",), {}),
        (
            (
                b"""
            <head></head><body>
            this isn't searched
            <meta charset="utf-8">
        """,
            ),
            {},
        ),
        (
            (
                b"""<meta http-equiv="Fake-Content-Type-Header" content="text/html; charset=utf-8">""",
            ),
            {},
        ),
        (("something else",), {}),
        (("""<meta charset="utf-8">""",), {}),
        (
            (
                """
            <head></head><body>
            this isn't searched
            <meta charset="utf-8">
        """,
            ),
            {},
        ),
        (
            (
                """<meta http-equiv="Fake-Content-Type-Header" content="text/html; charset=utf-8">""",
            ),
            {},
        ),
    ],
    resolve_encoding: [
        (("latin1",), {}),
        ((" Latin-1",), {}),
        (("gb_2312-80",), {}),
        (("unknown encoding",), {}),
    ],
    to_unicode: [
        ((b"\xc2\xa3", "utf-8"), {}),
        ((b"\xc2\xc2\xa3", "utf-8"), {}),
    ],
    html_to_unicode: [
        (
            (
                "Content-Type: text/html; charset=cp1251",
                b"\xea\xe8\xf0\xe8\xeb\xeb\xe8\xf7\xe5\xf1\xea\xe8\xe9 \xf2\xe5\xea\xf1\xf2",
            ),
            {},
        ),
        (("Content-Type: text/html; charset=utf-8", b"\xc2\xa3"), {}),
        (("Content-Type: text/html; charset=iso-8859-1", b"\xa3"), {}),
        (("Content-Type: text/html; charset=", b"\xc2\xa3"), {}),
        (("Content-Type: text/html; charset=none", b"\xc2\xa3"), {}),
        (("Content-Type: text/html; charset=gb2312", b"\xa8D"), {}),
        (("Content-Type: text/html; charset=gbk", b"\xa8D"), {}),
        (("Content-Type: text/html; charset=big5", b"\xf9\xda"), {}),
        (
            (
                "Content-Type: text/html; charset=utf-8",
                b"\xef\xbb\xbfWORD\xe3\xabWORD2",
            ),
            {},
        ),
        ((None, b"\xef\xbb\xbfWORD\xe3\xabWORD2"), {}),
        (("Content-Type: text/html; charset=utf-8", b"\xef\xbb\xbfWORD\xe3\xab"), {}),
        ((None, b"\xef\xbb\xbfWORD\xe3\xab"), {}),
        (("Content-Type: text/html; charset=utf-8", b"PREFIX\xe3\xabSUFFIX"), {}),
        (("Content-Type: text/html; charset=utf-8", b"\xf0<span>value</span>"), {}),
        (("Content-Type: text/html; charset=utf-8", b"\xef\xbb\xbfhi"), {}),
        ((None, b"\xef\xbb\xbfhi"), {}),
        (("Content-Type: text/html; charset=utf-16", b"\xfe\xff\x00h\x00i"), {}),
        ((None, b"\xfe\xff\x00h\x00i"), {}),
        (("Content-Type: text/html; charset=utf-16", b"\xff\xfeh\x00i\x00"), {}),
        ((None, b"\xff\xfeh\x00i\x00"), {}),
        (
            (
                "Content-Type: text/html; charset=utf-32",
                b"\x00\x00\xfe\xff\x00\x00\x00h\x00\x00\x00i",
            ),
            {},
        ),
        ((None, b"\x00\x00\xfe\xff\x00\x00\x00h\x00\x00\x00i"), {}),
        (
            (
                None,
                b"""blah blah < meta   http-equiv="Content-Type"
            content="text/html; charset=iso-8859-1"> other stuff""",
            ),
            {},
        ),
        (
            (
                "Content-Type: text/html; charset=utf-8",
                b"""blah blah < meta   http-equiv="Content-Type"
            content="text/html; charset=iso-8859-1"> other stuff""",
            ),
            {},
        ),
        ((None, b"\xef\xbb\xbfblah blah"), {}),
        ((None, b"no encoding info"), {}),
        ((None, b""), {}),
    ],
}
BENCHMARK_CASES[html_encoding] = BENCHMARK_CASES[html_to_unicode]


@pytest.mark.parametrize("func", BENCHMARK_CASES)
def test_benchmark_encoding(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
) -> None:
    @benchmark
    def factory():
        for args, kwargs in BENCHMARK_CASES[func]:
            func(*args, **kwargs)


@pytest.mark.parametrize("func", BENCHMARK_CASES)
def test_benchmark_encoding_cold(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
) -> None:
    """Same cases as test_benchmark_encoding but with the resolve_encoding LRU
    cache cleared before every round."""

    def factory():
        for args, kwargs in BENCHMARK_CASES[func]:
            func(*args, **kwargs)

    benchmark.pedantic(factory, setup=resolve_encoding.cache_clear, rounds=100)


_PAGES = Path(__file__).parent / "pages"
_UTF8_PAGE = (_PAGES / "no-base.html").read_bytes()
# Real pages, one per legacy encoding, named after it. All declare it in a
# <meta> tag except windows-1251, which declares it in its Content-Type header.
_LEGACY_PAGES = {
    path.stem: path.read_bytes()
    for path in sorted((_PAGES / "encoding").glob("*.html"))
}
_META_CHARSET_RE = re.compile(rb"<meta[^>]*charset[^>]*>", re.IGNORECASE)
PAGE_CASES = {
    "utf-8": (None, _UTF8_PAGE),
    "utf-8-header": ("text/html; charset=utf-8", _UTF8_PAGE),
    "invalid-utf-8": (None, _UTF8_PAGE.replace(b"</div>", b"</div>\xff")),
    **{
        name: (
            "text/html; charset=windows-1251" if name == "windows-1251" else None,
            body,
        )
        for name, body in _LEGACY_PAGES.items()
    },
    **{
        f"undeclared-{name}": (None, _META_CHARSET_RE.sub(b"", _LEGACY_PAGES[name]))
        for name in ("shift_jis", "windows-1252")
    },
}


@pytest.mark.parametrize("func", [html_to_unicode, html_encoding])
@pytest.mark.parametrize(("content_type", "body"), PAGE_CASES.values(), ids=PAGE_CASES)
def test_benchmark_page(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
    content_type: str | None,
    body: bytes,
) -> None:
    benchmark(func, content_type, body)


def test_benchmark_import(benchmark: BenchmarkFixture) -> None:
    """Import w3lib.encoding and the Python modules of frostwork.

    The frostwork extension module cannot be imported again, so it stays
    loaded.
    """

    def setup() -> tuple[tuple[str], dict[str, Any]]:
        for name in ("w3lib.encoding", "frostwork.encoding", "frostwork"):
            sys.modules.pop(name, None)
        return ("w3lib.encoding",), {}

    benchmark.pedantic(importlib.import_module, setup=setup, rounds=20)
