from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from w3lib._url import _urlsplit
from w3lib.url import (
    add_or_replace_parameter,
    add_or_replace_parameters,
    any_to_uri,
    canonicalize_url,
    file_uri_to_path,
    is_url,
    parse_data_uri,
    parse_url,
    path_to_file_uri,
    safe_download_url,
    safe_url_string,
    url_query_cleaner,
    url_query_parameter,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-not-found]

    from tests.benchmarks import CasesMapType

BENCHMARK_CASES: CasesMapType = {
    parse_url: [
        (("http://example.com",), {}),
        (("https://example.com/path?x=1",), {}),
        (("ftp://user:pass@example.com:21/file.txt",), {}),
        ((b"http://example.com",), {}),
    ],
    canonicalize_url: [
        (("http://www.example.com",), {}),
        (("http://www.example.com/do?b=2&a=1",), {}),
        (("http://www.example.com/résumé?q=résumé",), {}),
        ((b"http://www.example.com/a do\xc2\xa3.html?a=1",), {}),
    ],
    file_uri_to_path: [
        (("file:///some/path.txt",), {}),
        (("file:///path/to/file",), {}),
        (("/path/to/file",), {}),
        (("test.txt",), {}),
    ],
    path_to_file_uri: [
        (("/some/path.txt",), {}),
        (("test.txt",), {}),
        (("./relative/path.txt",), {}),
    ],
    any_to_uri: [
        (("/some/path.txt",), {}),
        (("file:///some/path.txt",), {}),
        (("http://www.example.com/some/path.txt",), {}),
    ],
    safe_url_string: [
        (("\u8349\u8599 \u7d20\u5b50",), {}),
        (("©",), {}),
        (("©", "iso-8859-1"), {}),
        (("©",), {"path_encoding": "iso-8859-1"}),
        (("http://www.example.org/",), {}),
        (("/ecommerce/oggetto/Te \xf2/tea-strainer/1273",), {}),
        (("http://www.example.com/test?p(29)url(http://www.another.net/page)",), {}),
        (("http://www.example.com/Brochures_&_Paint_Cards&PageSize=200",), {}),
        (("http://www.example.com/£",), {}),
        (("http://www.example.com/£",), {"encoding": "utf-8"}),
        (("http://www.example.com/£",), {"encoding": "latin-1"}),
        (("http://www.example.com/£",), {"path_encoding": "latin-1"}),
        ((b"http://example.com/",), {}),
        (("http://example.com/test\n.html",), {}),
        (("http://example.com/test\t.html",), {}),
        (("http://example.com/test\r.html",), {}),
        (("http://example.com/test\r.html\n",), {}),
        (("http://example.com/test\r\n.html\t",), {}),
        (("http://example.com/test\a\n.html",), {}),
        (('http://google.com/"hello"',), {"quote_path": True}),
        (('http://google.com/"hello"',), {"quote_path": False}),
        (("http://www.example.com/£?unit=µ",), {}),
        (("http://www.example.com/£?unit=µ",), {"encoding": "utf-8"}),
        (("http://www.example.com/£?unit=µ",), {"encoding": "latin-1"}),
        (("http://www.example.com/£?unit=µ",), {"path_encoding": "latin-1"}),
        (
            ("http://www.example.com/£?unit=µ",),
            {"encoding": "latin-1", "path_encoding": "latin-1"},
        ),
        (("http://www.example.com/£?unit=%C2%B5",), {}),
        (("http://www.example.com/%C2%A3?unit=µ",), {}),
        ((b"http://www.example.com/",), {}),
        ((b"http://www.example.com/\xc2\xb5",), {}),
        ((b"http://www.example.com/\xb5",), {"encoding": "latin1"}),
        ((b"http://www.example.com/\xa3?unit=\xb5",), {"encoding": "latin1"}),
        ((b"http://www.example.com/\xa3?unit=\xb5",), {}),
        ((b"http://www.example.com/country/\xd0\xee\xf1\xf1\xe8\xff",), {}),
        (("http://.example.com/résumé?q=résumé",), {}),
        ((f"http://www.{'example' * 11}.com/résumé?q=résumé",), {}),
        (("http://www.example.com:80/résumé?q=résumé",), {}),
        (("http://www.example.com:/résumé?q=résumé",), {}),
        (("http://www.example.com/path/to/%23/foo/bar",), {}),
        (("http://www.example.com/path/to/%23/foo/bar#frag",), {}),
        (("http://新华网.中国:80",), {}),
        (("ftp://admin:admin@新华网.中国:21",), {}),
        (("http://Åsa:abc123@➡.ws:81/admin",), {}),
        (("http://japão:não@️i❤️.ws:8000/",), {}),
        (("ftp://admin:@新华网.中国:21",), {}),
        (("ftp://admin@新华网.中国:21",), {}),
        (("ftp://admin:|%@example.com",), {}),
        (("http://%25user:%25pass@host",), {}),
        (("http://%user:%pass@host",), {}),
        (("http://%26user:%26pass@host",), {}),
        (("http://%2525user:%2525pass@host",), {}),
        (("http://%2526user:%2526pass@host",), {}),
        (("http://%25%26user:%25%26pass@host",), {}),
    ],
    safe_download_url: [
        (("http://www.example.org",), {}),
        (("http://www.example.org/../",), {}),
        (("http://www.example.org/../../images/../image",), {}),
        (("http://www.example.org/dir/",), {}),
        ((b"http://www.example.org/dir/",), {}),
        (
            (b"http://www.example.org?\xa3",),
            {"encoding": "latin-1", "path_encoding": "latin-1"},
        ),
        (
            (b"http://www.example.org?\xc2\xa3",),
            {"encoding": "utf-8", "path_encoding": "utf-8"},
        ),
        (
            (b"http://www.example.org/\xc2\xa3?\xc2\xa3",),
            {"encoding": "utf-8", "path_encoding": "latin-1"},
        ),
    ],
    is_url: [
        (("http://www.example.org",), {}),
        (("https://www.example.org",), {}),
        (("file:///some/path",), {}),
        (("foo://bar",), {}),
        (("foo--bar",), {}),
    ],
    url_query_parameter: [
        (("product.html?id=200&foo=bar", "id"), {}),
        (("product.html?id=200&foo=bar", "notthere", "mydefault"), {}),
        (("product.html?id=", "id"), {}),
        (("product.html?id=", "id"), {"keep_blank_values": 1}),
    ],
    add_or_replace_parameter: [
        (("http://domain/test", "arg", "v"), {}),
        (("http://domain/test?arg1=v1&arg2=v2&arg3=v3", "arg4", "v4"), {}),
        (("http://domain/test?arg1=v1&arg2=v2&arg3=v3", "arg3", "nv3"), {}),
        (("http://domain/moreInfo.asp?prodID=", "prodID", "20"), {}),
        (
            (
                "http://rmc-offers.co.uk/productlist.asp?BCat=2%2C60&CatID=60",
                "BCat",
                "newvalue",
            ),
            {},
        ),
        (
            (
                "http://rmc-offers.co.uk/productlist.asp?BCat=2,60&CatID=60",
                "BCat",
                "newvalue",
            ),
            {},
        ),
        (("http://rmc-offers.co.uk/productlist.asp?", "BCat", "newvalue"), {}),
        (
            (
                "http://example.com/?version=1&pageurl=http%3A%2F%2Fwww.example.com%2Ftest%2F%23fragment%3Dy&param2=value2",
                "version",
                "2",
            ),
            {},
        ),
        (
            (
                "http://example.com/?version=1&pageurl=http%3A%2F%2Fwww.example.com%2Ftest%2F%23fragment%3Dy&param2=value2",
                "pageurl",
                "test",
            ),
            {},
        ),
        (("http://domain/test?arg1=v1&arg2=v2&arg1=v3", "arg4", "v4"), {}),
        (("http://domain/test?arg1=v1&arg2=v2&arg1=v3", "arg1", "v3"), {}),
    ],
    add_or_replace_parameters: [
        (("http://domain/test", {"arg": "v"}), {}),
        (("http://domain/test?arg1=v1&arg2=v2&arg3=v3", {"arg4": "v4"}), {}),
        (
            (
                "http://domain/test?arg1=v1&arg2=v2&arg3=v3",
                {"arg4": "v4", "arg3": "v3new"},
            ),
            {},
        ),
        (("http://domain/test?arg1=v1&arg2=v2&arg1=v3", {"arg4": "v4"}), {}),
        (("http://domain/test?arg1=v1&arg2=v2&arg1=v3", {"arg1": "v3"}), {}),
    ],
    url_query_cleaner: [
        (("product.html?",), {}),
        (("product.html?&",), {}),
        (("product.html?id=200&foo=bar&name=wired", ["id"]), {}),
        (("product.html?&id=200&&foo=bar&name=wired", ["id"]), {}),
        (("product.html?foo=bar&name=wired", ["id"]), {}),
        (("product.html?id=200&foo=bar&name=wired", ["id", "name"]), {}),
        (("product.html?id&other=3&novalue=", ["id"]), {}),
        (("product.html?d=1&e=b&d=2&d=3&other=other", ["d"]), {}),
        (("product.html?d=1&e=b&d=2&d=3&other=other", ["d"]), {"unique": False}),
        (("product.html?id=200&foo=bar&name=wired#id20", ["id", "foo"]), {}),
        (("product.html?id=200&foo=bar&name=wired", ["id"]), {"remove": True}),
        (("product.html?id=2&foo=bar&name=wired", ["id", "foo"]), {"remove": True}),
        (("product.html?id=2&foo=bar&name=wired", ["id", "footo"]), {"remove": True}),
        (("product.html", ["id"]), {"remove": True}),
        (("product.html?&", ["id"]), {"remove": True}),
        (("product.html?foo=bar&name=wired", "foo"), {}),
        (("product.html?foo=bar&foobar=wired", "foobar"), {}),
        (
            ("product.html?id=200&foo=bar&name=wired#foo", ["id"]),
            {"keep_fragments": True},
        ),
        (("product.html?id=200&foo=bar&name=wired", ["id"]), {"keep_fragments": True}),
    ],
    parse_data_uri: [
        (("data:,A%20brief%20note",), {}),
        ((b"data:,A%20brief%20note",), {}),
        (("data:,é",), {}),
        (("data:text/plain;base64,SGVsb G8sIH\n  dvcm   xk Lg%3D\n%3D",), {}),
        (
            (
                "data:text/plain;"
                "foo=%22foo;bar%5C%22%22;"
                "charset=utf-8;"
                "bar=%22foo;%5C%22foo%20;/%20,%22,"
                "%CE%8E%CE%A3%CE%8E",
            ),
            {},
        ),
        (
            (
                "data:text/plain;base64,SGVsb%20G8sIH%0A%20%20dvcm%20%20%20xk%20Lg%3D%0A%3D",
            ),
            {},
        ),
        (("DATA:,A%20brief%20note",), {}),
        (("DaTa:,A%20brief%20note",), {}),
    ],
}


@pytest.mark.parametrize("func", BENCHMARK_CASES)
def test_benchmark_url(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
) -> None:
    @benchmark
    def factory():
        for args, kwargs in BENCHMARK_CASES[func]:
            func(*args, **kwargs)


@pytest.mark.parametrize("func", BENCHMARK_CASES)
def test_benchmark_url_cold(
    benchmark: BenchmarkFixture,
    func: Callable[..., Any],
) -> None:
    """Same cases as test_benchmark_url but with the _urlsplit LRU cache
    cleared before every round."""

    def factory():
        for args, kwargs in BENCHMARK_CASES[func]:
            func(*args, **kwargs)

    benchmark.pedantic(factory, setup=_urlsplit.cache_clear, rounds=100)
