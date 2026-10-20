from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from w3lib.url import _urljoin, safe_url_string

_KNOWN_FAILURES: set[tuple[str | None, str]] = {
    (None, "https://test:@test"),
    (None, "https://:@test"),
    (None, "non-special://test:@test/x"),
    (None, "non-special://:@test/x"),
    (None, "file://example:1/"),
    (None, "file:///w|/m"),
    (None, "file:C|/m/"),
    (None, "file:C||/m/"),
    (None, "http://user:pass@/"),
    (None, "http://foo:80/"),
    (None, "https://foo:443/"),
    (None, "ftp://foo:21/"),
    (None, "ws://foo:80/"),
    (None, "wss://foo:443/"),
    (None, "http:@www.example.com"),
    (None, "http:/@www.example.com"),
    (None, "http://@www.example.com"),
    (None, "http://@pple.com"),
    (None, "http:/:@/www.example.com"),
    (None, "http://user@/www.example.com"),
    (None, "http:@/www.example.com"),
    (None, "http:/@/www.example.com"),
    (None, "http://@/www.example.com"),
    (None, "https:@/www.example.com"),
    (None, "http:a:b@/www.example.com"),
    (None, "http:/a:b@/www.example.com"),
    (None, "http://a:b@/www.example.com"),
    (None, "http::@/www.example.com"),
    (None, "http:a:@www.example.com"),
    (None, "http:/a:@www.example.com"),
    (None, "http://a:@www.example.com"),
    (None, "http://:@www.example.com"),
    (None, "file:."),
    (None, "https://�"),
    (None, "https://faß.ExAmPlE/"),
    (None, "file:\\\\localhost//"),
    (None, "file://localhost//a//../..//"),
    (None, "file:/C|/"),
    (None, "file://C|/"),
    (None, "\\\\\\.\\Y:"),
    (None, "\\\\\\.\\y:"),
    (None, "file://localhost//a//../..//foo"),
    (None, "file://localhost////foo"),
    (None, "file:.//p"),
    (None, "http://?"),
    (None, "http://#"),
    (None, "non-special://[1:2:0:0:5:0:0:0]/"),
    (None, "non-special://[1:2:0:0:0:0:0:3]/"),
    (None, "a"),
    (None, "a/"),
    (None, "a//"),
    (None, "file://loC𝐀𝐋𝐇𝐨𝐬𝐭/usr/bin"),
    (None, "file://\xad/p"),
    (None, "#"),
    (None, "?"),
    (None, "https://\uffffy"),
    (None, ""),
    (None, "https://\xad/"),
    ("http://example.org/foo/bar", "http://f:00000000000000000000080/c"),
    ("http://example.org/foo/bar", "http://&a:foo(b]c@d:2/"),
    ("http://example.org/foo/bar", "http://[::127.0.0.1]"),
    ("http://example.org/foo/bar", "http://[0:0:0:0:0:0:13.1.68.3]"),
    ("http://example.org/foo/bar", "http://[2001::1]:80"),
    ("file:///tmp/mock/path", "file:c:\\foo\\bar.html"),
    ("file:///tmp/mock/path", "  File:c|////foo\\bar.html"),
    ("file:///tmp/mock/path", "C|/foo/bar"),
    ("file:///tmp/mock/path", "/C|\\foo\\bar"),
    ("file:///tmp/mock/path", "//C|/foo/bar"),
    ("file:///tmp/mock/path", "file://localhost"),
    ("file:///tmp/mock/path", "file://localhost/"),
    ("file:///tmp/mock/path", "file://localhost/test"),
    ("http://www.example.com/test", "file:..."),
    ("http://www.example.com/test", "file:.."),
    ("http://www.example.com/test", "file:a"),
    ("http://www.example.com/test", "file:."),
    ("http://other.com/", "http://\ufdd0zyx.com"),
    ("http://other.com/", "http://[::%31]"),
    ("https://example.org/foo/bar", "http:"),
    ("file:///C:/", ".."),
    ("file:///C:/a/b", "/"),
    ("file://h/C:/a/b", "/"),
    ("file:///C:/a/b", "//d:"),
    ("file:///C:/a/b", "//d:/.."),
    ("file://lion/", "\\/localhost//pig"),
    ("file://lion/", "//localhost//pig"),
    ("file://host/dir/file", "C|"),
    ("file://host/D:/dir1/dir2/file", "C|"),
    ("file://host/dir/file", "C|#"),
    ("file://host/dir/file", "C|?"),
    ("file://host/dir/file", "C|/"),
    ("file://host/dir/file", "C|\n/"),
    ("file://host/dir/file", "C|\\"),
    ("file:///c:/baz/qux", "/c|/foo/bar"),
    ("file://x/C:/", ".."),
    ("file://host/", "C|/"),
    ("file://host/", "//C:/"),
    ("file://host/", "file://C:/"),
    ("http://example.net/", "http://[1:0::]"),
    ("http://example.org", "https://user:pass[\x7f@foo/bar"),
}


_DIVERGENCES: dict[tuple[str | None, str], str] = {}


def _params() -> list[Any]:
    path = Path(__file__).parent / "wpt" / "urltestdata.json"
    params = []
    for case in json.loads(path.read_text(encoding="utf-8")):
        if isinstance(case, str):
            continue
        key = (case["base"], case["input"])
        marks = []
        if key in _KNOWN_FAILURES:
            marks.append(pytest.mark.xfail(strict=True))
        elif key in _DIVERGENCES:
            marks.append(pytest.mark.xfail(strict=True, reason=_DIVERGENCES[key]))
        params.append(pytest.param(case, id=repr(key), marks=marks))
    return params


@pytest.mark.parametrize("case", _params())
def test_urltestdata(case: dict[str, Any]) -> None:
    def parse() -> str:
        if case["base"] is None:
            return safe_url_string(case["input"])
        return safe_url_string(_urljoin(case["base"], case["input"]))

    if case.get("failure"):
        with pytest.raises(ValueError):  # noqa: PT011
            parse()
    else:
        assert parse() == safe_url_string(case["href"])
