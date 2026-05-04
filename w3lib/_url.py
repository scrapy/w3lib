from __future__ import annotations

import functools
import os
import string
import sys
from typing import TYPE_CHECKING
from urllib.parse import (
    ParseResult,
    SplitResult,
    scheme_chars,
    uses_netloc,
    uses_params,
)

from w3lib._infra import _ASCII_TAB_OR_NEWLINE, _C0_CONTROL_OR_SPACE

if TYPE_CHECKING:
    from urllib.parse import _QueryType

_IS_WINDOWS = os.name == "nt"
_IS_LINUX = sys.platform == "linux"
if _IS_LINUX:
    from urllib.parse import (  # type: ignore[attr-defined]
        _check_bracketed_netloc,
        _checknetloc,
    )
else:
    from urllib.parse import urlsplit as urllib_urlsplit

_FS_ENCODING = sys.getfilesystemencoding()
_FS_ERRORS = sys.getfilesystemencodeerrors()

# https://url.spec.whatwg.org/
# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#default-port
_DEFAULT_PORTS = {
    "ftp": 21,
    "file": None,
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
}
_SPECIAL_SCHEMES = set(_DEFAULT_PORTS.keys())

# constants from RFC 3986, Section 2.2 and 2.3
RFC3986_GEN_DELIMS = b":/?#[]@"
RFC3986_SUB_DELIMS = b"!$&'()*+,;="
RFC3986_RESERVED = RFC3986_GEN_DELIMS + RFC3986_SUB_DELIMS
RFC3986_UNRESERVED = (string.ascii_letters + string.digits + "-._~").encode("ascii")
EXTRA_SAFE_CHARS = b"|"  # see https://github.com/scrapy/w3lib/pull/25

RFC3986_USERINFO_SAFE_CHARS = RFC3986_UNRESERVED + RFC3986_SUB_DELIMS + b":"
_SAFE_CHARS = RFC3986_RESERVED + RFC3986_UNRESERVED + EXTRA_SAFE_CHARS + b"%"
_PATH_SAFE_CHARS = _SAFE_CHARS.replace(b"#", b"")
_PATH_SAFE_CHARS_STR = _PATH_SAFE_CHARS.decode()
_USES_NETLOC = frozenset(uses_netloc)
_SCHEME_CHARS = frozenset(scheme_chars)
_USES_PARAMS = frozenset(uses_params)


@functools.cache
def _hex_encode_table() -> bytes:
    return b"".join(f"%{i:02X}".encode() for i in range(256))


@functools.cache
def _safe_table(safe: bytes) -> bytes:
    table = bytearray(256)
    for b in safe:
        table[b] = 1
    return bytes(table)


@functools.cache
def _hex_decode_table() -> bytes:
    table = bytearray([255]) * 256
    table[48:58] = bytes(range(10))  # '0'-'9'
    table[65:71] = bytes(range(10, 16))  # 'A'-'F'
    table[97:103] = bytes(range(10, 16))  # 'a'-'f'
    return bytes(table)


def _quote(data: bytes, safe: bytes = b"") -> bytes:
    """faster version of urlib.parse.quote and without _coerce_args/_coerce_result"""
    if not data:
        return b""

    hex_table = _hex_encode_table()
    allowed = (
        _safe_table(RFC3986_UNRESERVED + safe)
        if safe
        else _safe_table(RFC3986_UNRESERVED)
    )

    output = bytearray()

    for byte in data:
        if allowed[byte]:
            output.append(byte)
        else:
            offset = byte * 3
            output += hex_table[offset : offset + 3]

    return bytes(output)


def _quote_into(data: bytes, safe: bytes, out: bytearray) -> None:
    hex_table = _hex_encode_table()
    allowed = (
        _safe_table(RFC3986_UNRESERVED + safe)
        if safe
        else _safe_table(RFC3986_UNRESERVED)
    )

    for byte in data:
        if allowed[byte]:
            out.append(byte)
        else:
            offset = byte * 3
            out.extend(hex_table[offset : offset + 3])


def _quote_plus(data: bytes) -> bytes:
    if not data:
        return b""

    hex_table = _hex_encode_table()
    safe_table = _safe_table(RFC3986_UNRESERVED)

    out = bytearray()

    for b in data:
        if b == 32:  # ' '
            out.append(43)  # '+'
        elif safe_table[b]:
            out.append(b)
        else:
            offset = b * 3
            out += hex_table[offset : offset + 3]

    return bytes(out)


def _unquote_plus(data: bytes) -> bytes:
    if not data:
        return b""

    hex_table = _hex_decode_table()
    out = bytearray()

    i = 0
    n = len(data)

    while i < n:
        b = data[i]

        if b == 43:  # '+'
            out.append(32)
            i += 1
            continue

        if b == 37 and i + 2 < n:
            hi = hex_table[data[i + 1]]
            lo = hex_table[data[i + 2]]

            if hi != 255 and lo != 255:
                out.append((hi << 4) | lo)
                i += 3
                continue

        out.append(b)
        i += 1

    return bytes(out)


def _parse_qs(
    qs: str | bytes, keep_blank_values: bool = False
) -> dict[bytes, list[bytes]]:
    if not qs:
        return {}

    if isinstance(qs, str):
        qs = qs.encode()

    result: dict[bytes, list[bytes]] = {}

    for field in qs.split(b"&"):
        if not field:
            continue

        i = field.find(b"=")

        if i == -1:
            if not keep_blank_values:
                continue
            key = field
            value = b""
        else:
            key = field[:i]
            value = field[i + 1 :]

            if not value and not keep_blank_values:
                continue

        key = _unquote_plus(key)
        value = _unquote_plus(value)

        if key in result:
            result[key].append(value)
        else:
            result[key] = [value]

    return result


def _parse_qsl(
    qs: str | bytes, keep_blank_values: bool = False
) -> list[tuple[bytes, bytes]]:
    if not qs:
        return []

    if isinstance(qs, str):
        qs = qs.encode()

    result: list[tuple[bytes, bytes]] = []

    for field in qs.split(b"&"):
        if not field:
            continue

        i = field.find(b"=")

        if i == -1:
            if not keep_blank_values:
                continue
            key = field
            value = b""
        else:
            key = field[:i]
            value = field[i + 1 :]

            if not value and not keep_blank_values:
                continue

        result.append((_unquote_plus(key), _unquote_plus(value)))

    return result


def _splitparams(url: str) -> tuple[str, str]:
    if "/" in url:
        i = url.find(";", url.rfind("/"))
        if i < 0:
            return url, ""
    else:
        i = url.find(";")
    return url[:i], url[i + 1 :]


def _urlencode(query: _QueryType) -> bytes:
    if hasattr(query, "items"):
        query = query.items()  # type: ignore[assignment]

    if not query:
        return b""

    result: list[bytes] = []

    for key, value in query:  # type: ignore[str-unpack]
        result.append(
            _quote_plus(key if isinstance(key, bytes) else str(key).encode())
            + b"="
            + _quote_plus(value if isinstance(value, bytes) else str(value).encode())
        )

    return b"&".join(result)


def _unquote(
    data: bytes | bytearray | str,
    safe: bytes = b"",
) -> bytes:
    """faster version of urlib.parse.unquote and without _coerce_args/_coerce_result"""
    if not data:
        return b""

    if isinstance(data, str):
        data = data.encode()

    hex_table = _hex_decode_table()
    allowed = _safe_table(safe) if safe else None

    output = bytearray()

    i = 0
    length = len(data)

    while i < length:
        byte = data[i]

        if byte == 37 and i + 2 < length:  # ord('%') = 37
            hi = hex_table[data[i + 1]]
            lo = hex_table[data[i + 2]]

            if hi != 255 and lo != 255:
                decoded = (hi << 4) | lo

                if allowed is None or not allowed[decoded]:
                    output.append(decoded)
                    i += 3
                    continue

        output.append(byte)
        i += 1

    return bytes(output)


def _urlparse(
    url: str,
    scheme: str = "",
    allow_fragments: bool = True,
) -> ParseResult:
    """urlib.parse.urlparse but without _coerce_args/_coerce_result"""
    if not url:
        return ParseResult(scheme, "", "", "", "", "")

    splitresult = _urlsplit(url, scheme, allow_fragments)
    scheme, netloc, url, query, fragment = splitresult
    if scheme in _USES_PARAMS and ";" in url:
        url, params = _splitparams(url)
    else:
        params = ""
    return ParseResult(scheme, netloc, url, params, query, fragment)


def _urlunparse(
    scheme: str,
    netloc: str,
    url: str,
    params: str,
    query: str,
    fragment: str,
) -> str:
    """urlib.parse.urlunparse but without _coerce_args/_coerce_result"""
    if params:
        url = f"{url};{params}"
    return _urlunsplit((scheme, netloc, url, query, fragment))


def _urlunsplit(components: tuple[str, str, str, str, str]) -> str:
    """urlib.parse.urlunsplit but without _coerce_args/_coerce_result"""
    scheme, netloc, url, query, fragment = components

    if netloc:
        if url and url[:1] != "/":
            url = "/" + url
        url = "//" + netloc + url
    elif url[:2] == "//" or (
        scheme and scheme in _USES_NETLOC and (not url or url[:1] == "/")
    ):
        url = "//" + url
    if scheme:
        url = scheme + ":" + url
    if query:
        url += "?" + query
    if fragment:
        url += "#" + fragment

    return url


@functools.lru_cache(typed=True)
def _urlsplit(
    url: str,
    scheme: str = "",
    allow_fragments: bool = True,
) -> SplitResult:
    """urllib.parse.urlsplit but without _coerce_args/_coerce_result"""

    if not url:
        return SplitResult(scheme, "", "", "", "")

    url = url.lstrip(_C0_CONTROL_OR_SPACE)
    scheme = scheme.strip(_C0_CONTROL_OR_SPACE)

    for char in _ASCII_TAB_OR_NEWLINE:
        if char in url:
            url = url.replace(char, "")
        if char in scheme:
            scheme = scheme.replace(char, "")

    netloc = query = fragment = ""

    scheme_sep_idx = url.find(":")
    if scheme_sep_idx > 0 and url[0].isascii() and url[0].isalpha():
        for c in url[:scheme_sep_idx]:
            if c not in _SCHEME_CHARS:
                break
        else:
            scheme, url = url[:scheme_sep_idx].lower(), url[scheme_sep_idx + 1 :]

    if url[:2] == "//":
        delim = len(url)
        for char in "/?#":
            wdelim = url.find(char, 2)
            if wdelim >= 0:
                delim = min(delim, wdelim)
        netloc, url = url[2:delim], url[delim:]

        has_opening = "[" in netloc
        has_closing = "]" in netloc
        if (has_opening and not has_closing) or (has_closing and not has_opening):
            raise ValueError("Invalid IPv6 URL")
        if has_opening and has_closing:
            _check_bracketed_netloc(netloc)
    _checknetloc(netloc)

    if allow_fragments and "#" in url:
        url, _, fragment = url.partition("#")

    if "?" in url:
        url, _, query = url.partition("?")

    return SplitResult(scheme, netloc, url, query, fragment)


if not _IS_LINUX:
    _urlsplit = urllib_urlsplit  # type: ignore[assignment]


def _url2pathname(url: str) -> str:
    """urllib.request.url2pathname but with faster _unquote"""
    if not url:
        return ""

    if url[:2] == "///":
        url = url[2:]
    elif url[11:] == "//localhost/":
        url = url[11:]

    if not _IS_WINDOWS:
        if "%" not in url:
            return url

        return _unquote(url, _PATH_SAFE_CHARS).decode(_FS_ENCODING, _FS_ERRORS)

    if url[:3] == "///":
        url = url[1:]
    url = url.replace(":", "|")
    if "|" not in url:
        return _unquote(url.replace("/", "\\").encode(), _PATH_SAFE_CHARS).decode(
            _FS_ENCODING, _FS_ERRORS
        )
    comp = url.split("|")
    if len(comp) != 2 or comp[0][-1] not in string.ascii_letters:
        raise OSError(f"Bad URL: {url}")
    drive = comp[0][-1].upper()
    tail = _unquote(comp[1].replace("/", "\\"), _PATH_SAFE_CHARS).decode(
        _FS_ENCODING, _FS_ERRORS
    )
    return f"{drive}:{tail}"
