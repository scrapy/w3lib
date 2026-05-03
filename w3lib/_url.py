import functools
import os
import string
import sys

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
_SPECIAL_SCHEMES = frozenset(_DEFAULT_PORTS.keys())

# constants from RFC 3986, Section 2.2 and 2.3
RFC3986_GEN_DELIMS = b":/?#[]@"
RFC3986_SUB_DELIMS = b"!$&'()*+,;="
RFC3986_RESERVED = RFC3986_GEN_DELIMS + RFC3986_SUB_DELIMS
RFC3986_UNRESERVED = (string.ascii_letters + string.digits + "-._~").encode("ascii")
EXTRA_SAFE_CHARS = b"|"  # see https://github.com/scrapy/w3lib/pull/25

RFC3986_USERINFO_SAFE_CHARS = RFC3986_UNRESERVED + RFC3986_SUB_DELIMS + b":"
_safe_chars = RFC3986_RESERVED + RFC3986_UNRESERVED + EXTRA_SAFE_CHARS + b"%"
_path_safe_chars = _safe_chars.replace(b"#", b"")
_path_safe_chars_str = _path_safe_chars.decode()


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


def _unquote(
    data: bytes | bytearray | str,
    safe: bytes = b"",
) -> bytes:
    if not data:
        return b""

    if isinstance(data, str):
        data = data.encode("utf8")

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


def _urlunparse(
    scheme: str,
    netloc: str,
    path: str,
    params: str,
    query: str,
    fragment: str,
) -> str:
    url = ""

    if scheme:
        url = scheme + ":"
    if netloc:
        url += "//" + netloc
    url += path
    if params:
        url += ";" + params
    if query:
        url += "?" + query
    if fragment:
        url += "#" + fragment

    return url


def _urlunsplit(components: tuple[str, str, str, str, str]) -> str:
    scheme, netloc, path, query, fragment = components

    if netloc:
        if path and path[0] != "/":
            path = "/" + path
        url = "//" + netloc + path
    elif path[:2] == "//" or (scheme and path[0] == "/"):
        url = "//" + path
    else:
        url = path
    if scheme:
        url = scheme + ":" + url
    if query:
        url += "?" + query
    if fragment:
        url += "#" + fragment

    return url


_IS_WINDOWS = os.name == "nt"


def _url2pathname(url: str) -> str:
    if not url:
        return ""

    if url[:2] == "///":
        url = url[2:]
    elif url[11:] == "//localhost/":
        url = url[11:]

    if not _IS_WINDOWS:
        if "%" not in url:
            return url

        return _unquote(url, _path_safe_chars).decode(_FS_ENCODING, _FS_ERRORS)

    if url[:2] == "///":
        url = url[1:]

    url = url.replace(":", "|")

    if "|" not in url:
        return _unquote(url.replace("/", "\\"), _path_safe_chars).decode(
            _FS_ENCODING, _FS_ERRORS
        )

    i = url.find("|")
    if i <= 0:
        raise OSError(f"Bad URL: {url}")

    drive_part = url[:i]
    tail_part = url[i + 1 :]

    drive_char = drive_part[-1]
    if not drive_char.isascii() or not drive_char.isalpha():
        raise OSError(f"Bad URL: {url}")

    drive = drive_char.upper()
    tail = _unquote(tail_part.replace("/", "\\"), _path_safe_chars).decode(
        _FS_ENCODING, _FS_ERRORS
    )

    return f"{drive}:{tail}"
