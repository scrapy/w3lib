from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from w3lib.url import _urljoin, safe_url_string

_KNOWN_FAILURES: set[tuple[str | None, str]] = {
    (None, "file://example:1/"),
    (None, "file:C|/m/"),
    (None, "file:C||/m/"),
    (None, "http://user:pass@/"),
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
    (None, "file:."),
    (None, "https://�"),
    (None, "file:\\\\localhost//"),
    (None, "file:/C|/"),
    (None, "\\\\\\.\\Y:"),
    (None, "\\\\\\.\\y:"),
    (None, "file:.//p"),
    (None, "http://?"),
    (None, "http://#"),
    (None, "a"),
    (None, "a/"),
    (None, "a//"),
    (None, "file://\xad/p"),
    (None, "#"),
    (None, "?"),
    (None, "https://\uffffy"),
    (None, ""),
    (None, "https://\xad/"),
    ("file:///tmp/mock/path", "file:c:\\foo\\bar.html"),
    ("file:///tmp/mock/path", "  File:c|////foo\\bar.html"),
    ("file:///tmp/mock/path", "C|/foo/bar"),
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
    ("file://host/dir/file", "C|"),
    ("file://host/D:/dir1/dir2/file", "C|"),
    ("file://host/dir/file", "C|#"),
    ("file://host/dir/file", "C|?"),
    ("file://host/dir/file", "C|/"),
    ("file://host/dir/file", "C|\n/"),
    ("file://host/dir/file", "C|\\"),
    ("file://x/C:/", ".."),
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
