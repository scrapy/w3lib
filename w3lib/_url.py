from __future__ import annotations

import dataclasses
import functools
import ipaddress
import os
import re
import string
import sys
import unicodedata
from typing import TYPE_CHECKING
from urllib.parse import ParseResult, scheme_chars, uses_netloc, uses_params

from w3lib._infra import _ASCII_TAB_OR_NEWLINE, _C0_CONTROL_OR_SPACE

if TYPE_CHECKING:
    from collections.abc import Generator
    from urllib.parse import _QueryType

_IS_WINDOWS = os.name == "nt"


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
_ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE = str.maketrans("", "", _ASCII_TAB_OR_NEWLINE)
_C0_CONTROL_OR_SPACE_SET = frozenset(_C0_CONTROL_OR_SPACE)
_C0_CONTROL_OR_SPACE_RE = re.compile(rf"[{_C0_CONTROL_OR_SPACE}]")
_SCHEME_RE = re.compile(rf"^([{scheme_chars}]*):")

_IPV_FUTURE_RE = re.compile(r"\Av[a-fA-F0-9]+\..+\Z")
_NETLOC_DELIMS_RE = re.compile(r"[/?#@:]")
_NETLOC_STRIP_CHARS = str.maketrans("", "", "@:#?")


def _strip(input_string: str) -> str:
    if not input_string:
        return input_string

    if (
        input_string[0] not in _C0_CONTROL_OR_SPACE_SET
        and input_string[-1] not in _C0_CONTROL_OR_SPACE_SET
        and not _C0_CONTROL_OR_SPACE_RE.search(input_string)
    ):
        return input_string

    return input_string.strip(_C0_CONTROL_OR_SPACE).translate(
        _ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE
    )


@functools.cache
def _hex_encode_table() -> bytes:
    return b"".join(f"%{i:02X}".encode() for i in range(256))


@functools.cache
def _hex_decode_table() -> bytes:
    table = bytearray([255]) * 256
    table[48:58] = bytes(range(10))  # '0'-'9'
    table[65:71] = bytes(range(10, 16))  # 'A'-'F'
    table[97:103] = bytes(range(10, 16))  # 'a'-'f'
    return bytes(table)


@functools.cache
def _safe_table(safe: bytes = RFC3986_UNRESERVED) -> bytes:
    table = bytearray(256)
    for b in safe:
        table[b] = 1
    return bytes(table)


@functools.cache
def _quote_table(safe: bytes = b"", quote_plus: bool = False) -> tuple[bytes, ...]:
    hex_table = _hex_encode_table()
    allowed = _safe_table(RFC3986_UNRESERVED + safe) if safe else _safe_table()
    output: list[bytes] = [b""] * 256

    for idx, byte in enumerate(range(256)):
        if allowed[byte]:
            output[idx] = chr(byte).encode()
        elif quote_plus and byte == 32:  # ord(' ')
            output[idx] = b"+"
        else:
            offset = byte * 3
            output[idx] = hex_table[offset : offset + 3]

    return tuple(output)


def _quote(data: bytes, safe: bytes = b"", quote_plus: bool = False) -> bytes:
    """faster version of urlib.parse.quote and without _coerce_args/_coerce_result"""
    if not data:  # pragma: no cover
        return b""

    transform_table = _quote_table(safe, quote_plus)
    return b"".join([transform_table[byte] for byte in data])


def _quote_into(
    data: bytes, output: bytearray, safe: bytes = b"", quote_plus: bool = False
) -> None:
    if not data:  # pragma: no cover
        return

    transform_table = _quote_table(safe, quote_plus)
    output += b"".join([transform_table[byte] for byte in data])


def _unquote(
    data: bytes | bytearray | str,
    safe: bytes = b"",
) -> bytes:
    if not data:
        return b""

    if isinstance(data, str):
        data = data.encode()

    first_percent = data.find(b"%")

    if first_percent < 0:
        return bytes(data)

    hex_decode_table = _hex_decode_table()
    safe_table = _safe_table(safe)

    data_length = len(data)
    decode_limit = data_length - 2

    output = bytearray(data_length)
    output[:first_percent] = data[:first_percent]

    input_index = first_percent
    output_index = first_percent

    while input_index < decode_limit:
        current_byte = data[input_index]

        if current_byte == 37:  # ord('%')
            high_nibble = hex_decode_table[data[input_index + 1]]
            low_nibble = hex_decode_table[data[input_index + 2]]

            if (high_nibble | low_nibble) != 255:
                decoded_byte = (high_nibble << 4) | low_nibble

                if not safe_table[decoded_byte]:
                    output[output_index] = decoded_byte
                    input_index += 3
                    output_index += 1
                    continue

        output[output_index] = current_byte
        input_index += 1
        output_index += 1

    while input_index < data_length:  # tail
        output[output_index] = data[input_index]
        input_index += 1
        output_index += 1

    return bytes(output[:output_index])


def _unquote_plus(
    data: bytes | bytearray | str,
) -> bytes:
    if not data:
        return b""

    if isinstance(data, str):
        data = data.encode()

    first_percent = data.find(b"%")
    first_plus = data.find(b"+")

    first_special = min(first_plus, first_percent)

    if first_special < 0:
        first_special = max(first_percent, first_plus)

    if first_special < 0:
        return bytes(data)

    hex_decode_table = _hex_decode_table()
    safe_table = _safe_table()

    data_length = len(data)
    decode_limit = data_length - 2

    output = bytearray(data_length)
    output[:first_special] = data[:first_special]

    input_index = first_special
    output_index = first_special

    while input_index < decode_limit:
        current_byte = data[input_index]

        if current_byte == 43:  # ord('+')
            output[output_index] = 32  # ord(' ')
            input_index += 1
            output_index += 1
            continue

        if current_byte == 37:  # ord('%')
            high_nibble = hex_decode_table[data[input_index + 1]]
            low_nibble = hex_decode_table[data[input_index + 2]]

            if (high_nibble | low_nibble) != 255:
                decoded_byte = (high_nibble << 4) | low_nibble

                if not safe_table[decoded_byte]:
                    output[output_index] = decoded_byte
                    input_index += 3
                    output_index += 1
                    continue

        output[output_index] = current_byte
        input_index += 1
        output_index += 1

    while input_index < data_length:  # tail
        current_byte = data[input_index]

        if current_byte == 43:  # ord('+')
            output[output_index] = 32  # ord(' ')
        else:
            output[output_index] = current_byte

        input_index += 1
        output_index += 1

    return bytes(output[:output_index])


def _parse_qs(
    qs: str | bytes,
    keep_blank_values: bool = False,
) -> dict[bytes, list[bytes]]:

    if not qs:  # pragma: no cover
        return {}

    if isinstance(qs, str):  # pragma: no cover
        qs = qs.encode()

    result: dict[bytes, list[bytes]] = {}

    for field in qs.split(b"&"):
        if not field:
            continue

        key, sep, value = field.partition(b"=")

        if not keep_blank_values and (not sep or not value):
            continue

        key = _unquote_plus(key)
        value = _unquote_plus(value)

        if key in result:
            result[key].append(value)
        else:
            result[key] = [value]

    return result


def _parse_qsl(
    qs: str | bytes,
    keep_blank_values: bool = False,
) -> list[tuple[bytes, bytes]]:

    if not qs:  # pragma: no cover
        return []

    if isinstance(qs, str):  # pragma: no cover
        qs = qs.encode()

    result: list[tuple[bytes, bytes]] = []

    for field in qs.split(b"&"):
        if not field:
            continue

        key, sep, value = field.partition(b"=")

        if not keep_blank_values and (not sep or not value):
            continue

        result.append((_unquote_plus(key), _unquote_plus(value)))

    return result


def _urlencode(query: _QueryType) -> bytes:
    if hasattr(query, "items"):  # pragma: no cover
        query = query.items()  # type: ignore[assignment]

    if not query:  # pragma: no cover
        return b""

    result: list[bytes] = []
    tmp_buf = bytearray()

    for key, value in query:  # type: ignore[str-unpack]
        _quote_into(
            key if isinstance(key, bytes) else str(key).encode(),
            output=tmp_buf,
            quote_plus=True,
        )
        tmp_buf.append(61)  # chr(61)
        _quote_into(
            value if isinstance(value, bytes) else str(value).encode(),
            output=tmp_buf,
            quote_plus=True,
        )
        result.append(bytes(tmp_buf))
        tmp_buf.clear()

    return b"&".join(result)


def _urlparse(
    url: str,
    scheme: str = "",
    allow_fragments: bool = True,
) -> ParseResult:
    """urlib.parse.urlparse but without _coerce_args/_coerce_result"""
    if not url:  # pragma: no cover
        return ParseResult(scheme, "", "", "", "", "")

    scheme, netloc, url, query, fragment = _urlsplit(url, scheme, allow_fragments)
    params = ""

    if scheme in _USES_PARAMS:
        semi_idx = url.find(";")

        if semi_idx != -1:
            slash_idx = url.rfind("/")

            if slash_idx != -1 and slash_idx < semi_idx:
                semi_idx = url.find(";", slash_idx)

            if semi_idx != -1:
                url, params = url[:semi_idx], url[semi_idx + 1 :]

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
    if params:  # pragma: no cover
        url = f"{url};{params}"
    return _urlunsplit((scheme, netloc, url, query, fragment))


def _urlunsplit(components: tuple[str, str, str, str, str]) -> str:
    """urlib.parse.urlunsplit but without _coerce_args/_coerce_result"""
    scheme, netloc, url, query, fragment = components

    if scheme:
        scheme = f"{scheme}:"

    if netloc:
        if url and url[:1] != "/":
            url = f"/{url}"
        url = f"//{netloc}{url}"
    elif url[:2] == "//" or (
        scheme and scheme in _USES_NETLOC and (not url or url[:1] == "/")
    ):
        url = f"//{url}"

    if query:
        query = f"?{query}"

    if fragment:
        fragment = f"#{fragment}"

    return f"{scheme}{url}{query}{fragment}"


@dataclasses.dataclass(slots=True, eq=False, repr=False)
class _SplitResult:  # pylint: disable=too-many-instance-attributes
    scheme: str
    netloc: str
    path: str
    query: str
    fragment: str

    username: str | None = None
    password: str | None = None
    hostname: str | None = None
    port: str | int | None = None

    def __post_init__(self) -> None:
        if self.hostname is not None:
            hostname, delim, zone = self.hostname.partition("%")
            self.hostname = f"{hostname.lower()}{delim}{zone}"

        if self.port is not None:
            try:
                self.port = int(self.port)
            except ValueError:
                raise ValueError(
                    f"Port could not be cast to integer value as {self.port}"
                ) from None

            if self.port not in range(65535 + 1):
                raise ValueError("Port out of range 0-65535")

    def __iter__(self) -> Generator[str]:
        yield self.scheme
        yield self.netloc
        yield self.path
        yield self.query
        yield self.fragment

    def __len__(self) -> int:
        return 5  # pragma: no cover

    def __getitem__(self, index: int) -> str:
        match index:
            case 0:
                return self.scheme
            case 1:
                return self.netloc
            case 2:
                return self.path
            case 3:
                return self.query
            case 4:
                return self.fragment
        raise IndexError


def _checknetloc(netloc: str) -> None:
    """
    Validate that NFKC normalization does not introduce reserved URL characters.

    Raises:
        ValueError: If normalization introduces reserved delimiters.
    """
    # Fast path for common cases.
    if not netloc or netloc.isascii():
        return

    # IDNA uses NFKC equivalence. Remove already-valid delimiters before
    # normalization so we only detect newly introduced ones.
    cleaned, normalized = _nfkc_netloc(netloc)

    # Fast path: no normalization changes.
    if cleaned == normalized:
        return

    if _NETLOC_DELIMS_RE.search(normalized):
        raise ValueError(
            f"netloc {netloc!r} contains invalid characters under NFKC normalization"
        )


def _check_bracketed_netloc(netloc: str) -> None:
    """
    Validate bracket usage in a URL netloc.

    Raises:
        ValueError: If bracket placement or host syntax is invalid.
    """
    # Must mirror NetlocResultMixins._hostinfo() splitting behavior.
    hostname_and_port = netloc.rpartition("@")[2]

    before_bracket, has_open_bracket, bracketed = hostname_and_port.partition("[")

    if has_open_bracket:
        # No data is allowed before '['.
        if before_bracket:
            raise ValueError("Invalid IPv6 URL")

        hostname, _, port = bracketed.partition("]")

        # Only ':<port>' may follow ']'.
        if port and not port.startswith(":"):
            raise ValueError("Invalid IPv6 URL")
    else:
        hostname, _, _ = hostname_and_port.partition(":")

    _check_bracketed_host(hostname)


def _check_bracketed_host(hostname: str) -> None:
    """
    Validate a bracketed host according to RFC 3986 / WHATWG URL rules.

    Raises:
        ValueError: If the host is invalid.
    """
    # IPvFuture: v<HEXDIG>.<address>
    if hostname.startswith(("v", "V")):
        if not _IPV_FUTURE_RE.fullmatch(hostname):
            raise ValueError("IPvFuture address is invalid")
        return

    # ip_address() raises ValueError if invalid.
    ip = ipaddress.ip_address(hostname)

    # Bracketed IPv4 literals are forbidden.
    if isinstance(ip, ipaddress.IPv4Address):
        raise ValueError("An IPv4 address cannot be in brackets")


@functools.lru_cache
def _urlsplit(  # pylint: disable=too-many-locals,too-many-statements
    url: str,
    scheme: str = "",
    allow_fragments: bool = True,
) -> _SplitResult:
    """urllib.parse.urlsplit but without _coerce_args/_coerce_result"""

    if not url:
        return _SplitResult(scheme, "", "", "", "")

    url, scheme = url.lstrip(_C0_CONTROL_OR_SPACE), scheme.strip(_C0_CONTROL_OR_SPACE)

    netloc = query = fragment = ""

    if m := _SCHEME_RE.match(url):
        scheme = m.group(1).lower()
        url = url[m.end() :]

    slash_pos = question_pos = hash_pos = open_br_pos = closing_br_pos = -1
    for idx, char in enumerate(url[2:], 2):
        if char == "/" and slash_pos == -1:
            slash_pos = idx
        elif char == "?" and question_pos == -1:
            question_pos = idx
        elif char == "#" and hash_pos == -1:
            hash_pos = idx
        elif char == "[" and open_br_pos == -1:
            open_br_pos = idx
        elif char == "]" and closing_br_pos == -1:
            closing_br_pos = idx
        if slash_pos != question_pos != hash_pos != open_br_pos != closing_br_pos != -1:
            break

    if url[:2] == "//":
        if (open_br_pos != -1) != (closing_br_pos != -1):
            raise ValueError("Invalid IPv6 URL")
        delim = len(url)

        if 0 < slash_pos < delim:
            delim = slash_pos
        if 0 < question_pos < delim:
            delim = question_pos
        if 0 < hash_pos < delim:
            delim = hash_pos

        netloc = url[2:delim]
        if open_br_pos != -1 and closing_br_pos != -1:
            _check_bracketed_netloc(netloc)

        url = url[delim:]

        if question_pos != -1:
            question_pos -= delim
        if hash_pos != -1:
            hash_pos -= delim
    _checknetloc(netloc)

    if allow_fragments and hash_pos != -1:
        url, fragment = url[:hash_pos], url[hash_pos + 1 :]

    if question_pos != -1:
        url, query = url[:question_pos], url[question_pos + 1 :]

    username = password = hostname = port = None
    userinfo, have_info, hostinfo = netloc.rpartition("@")

    if have_info:
        username, _, password = userinfo.partition(":")
        password = password if _ else None

    if open_br_pos != -1:
        bracketed = hostinfo.partition("[")[2]
        hostname, _, port = bracketed.partition("]")
        port = port.partition(":")[2]
    else:
        hostname, _, port = hostinfo.partition(":")

    return _SplitResult(
        scheme,
        netloc,
        url,
        query,
        fragment,
        username,
        password,
        hostname,
        port or None,
    )


def _url2pathname(url: str) -> str:
    """urllib.request.url2pathname but with faster _unquote"""
    if not url:  # pragma: no cover
        return ""

    if url[:3] == "///":
        url = url[2:]
    elif url[12:] == "//localhost/":
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


@functools.lru_cache
def _idna(input_string: str) -> tuple[bytes, str]:
    if input_string.isascii():
        return input_string.encode(), input_string

    _, normalized = _nfkc_netloc(input_string)

    encoded = normalized.encode("idna")
    return encoded, encoded.decode()


def _idna_bytes(input_string: str) -> bytes:
    return _idna(input_string)[0]


def _idna_str(input_string: str) -> str:
    return _idna(input_string)[1]


@functools.lru_cache
def _nfkc_netloc(netloc: str) -> tuple[str, str]:
    """
    Return:
        cleaned: delimiter-stripped input
        normalized: NFKC-normalized cleaned input
    """
    cleaned = netloc.translate(_NETLOC_STRIP_CHARS)
    normalized = unicodedata.normalize("NFKC", cleaned)
    return cleaned, normalized
