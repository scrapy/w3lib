"""
This module contains general purpose URL functions not found in the standard
library.
"""

from __future__ import annotations

import base64
import codecs
import os
import posixpath
import re
import string
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast, overload
from urllib.parse import (
    ParseResult,
    parse_qs,
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)
from urllib.request import pathname2url, url2pathname

from ._infra import _ASCII_TAB_OR_NEWLINE, _C0_CONTROL_OR_SPACE
from ._url import _SPECIAL_SCHEMES
from .util import to_unicode

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._types import AnyUnicodeError


# error handling function for bytes-to-Unicode decoding errors with URLs
def _quote_byte(error: UnicodeError) -> tuple[str, int]:
    error = cast("AnyUnicodeError", error)
    text = error.object[error.start : error.end]
    if isinstance(text, str):
        text = text.encode()
    return (to_unicode(_quote(text)), error.end)


codecs.register_error("percentencode", _quote_byte)

# constants from RFC 3986, Section 2.2 and 2.3
RFC3986_GEN_DELIMS = b":/?#[]@"
RFC3986_SUB_DELIMS = b"!$&'()*+,;="
RFC3986_RESERVED = RFC3986_GEN_DELIMS + RFC3986_SUB_DELIMS
RFC3986_UNRESERVED = (string.ascii_letters + string.digits + "-._~").encode("ascii")
EXTRA_SAFE_CHARS = b"|"  # see https://github.com/scrapy/w3lib/pull/25

RFC3986_USERINFO_SAFE_CHARS = RFC3986_UNRESERVED + RFC3986_SUB_DELIMS + b":"
_safe_chars = RFC3986_RESERVED + RFC3986_UNRESERVED + EXTRA_SAFE_CHARS + b"%"
_path_safe_chars = _safe_chars.replace(b"#", b"")

# Characters that are safe in all of:
#
# -   RFC 2396 + RFC 2732, as interpreted by Java 8’s java.net.URI class
# -   RFC 3986
# -   The URL living standard
#
# NOTE: % is currently excluded from these lists of characters, due to
# limitations of the current safe_url_string implementation, but it should also
# be escaped as %25 when it is not already being used as part of an escape
# character.
_USERINFO_SAFEST_CHARS = RFC3986_USERINFO_SAFE_CHARS.translate(None, delete=b":;=")
_PATH_SAFEST_CHARS = _safe_chars.translate(None, delete=b"#[]|")
_QUERY_SAFEST_CHARS = _PATH_SAFEST_CHARS
_SPECIAL_QUERY_SAFEST_CHARS = _PATH_SAFEST_CHARS.translate(None, delete=b"'")
_FRAGMENT_SAFEST_CHARS = _PATH_SAFEST_CHARS


_ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE = {
    ord(char): None for char in _ASCII_TAB_OR_NEWLINE
}


def _strip(url: str) -> str:
    return url.strip(_C0_CONTROL_OR_SPACE).translate(
        _ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE
    )


_SAFE = bytearray(256)
for c in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~":
    _SAFE[c] = 1

_HEX = [f"%{i:02X}".encode() for i in range(256)]


def _quote(data: bytes, safe: bytes | None = None) -> bytes:
    out = bytearray()
    for b in data:
        if _SAFE[b] or (safe is not None and b in safe):
            out.append(b)
        else:
            out += _HEX[b]

    return bytes(out)


_HEX_TABLE = [-1] * 256
for i in range(ord("0"), ord("9") + 1):
    _HEX_TABLE[i] = i - 48
for i in range(ord("A"), ord("F") + 1):
    _HEX_TABLE[i] = i - 55
for i in range(ord("a"), ord("f") + 1):
    _HEX_TABLE[i] = i - 87


def _unquote(
    s: bytes | bytearray | str,
    safe: bytes = b"",
) -> bytes:
    if not s:
        return b""

    if isinstance(s, str):
        s = s.encode("utf8")

    res = bytearray()

    i = 0
    n = len(s)

    while i < n:
        c = s[i]

        if c == 37 and i + 2 < n:  # '%'
            h1 = _HEX_TABLE[s[i + 1]]
            h2 = _HEX_TABLE[s[i + 2]]

            if h1 != -1 and h2 != -1:
                decoded = (h1 << 4) | h2

                if decoded not in safe:
                    res.append(decoded)
                    i += 3
                    continue

        res.append(c)
        i += 1

    return bytes(res)


def safe_url_string(
    url: str | bytes,
    encoding: str = "utf8",
    path_encoding: str = "utf8",
    quote_path: bool = True,
) -> str:
    """Return a URL equivalent to *url* that a wide range of web browsers and
    web servers consider valid.

    *url* is parsed according to the rules of the `URL living standard`_,
    and during serialization additional characters are percent-encoded to make
    the URL valid by additional URL standards.

    .. _URL living standard: https://url.spec.whatwg.org/

    The returned URL should be valid by *all* of the following URL standards
    known to be enforced by modern-day web browsers and web servers:

    -   `URL living standard`_

    -   `RFC 3986`_

    -   `RFC 2396`_ and `RFC 2732`_, as interpreted by `Java 8’s java.net.URI
        class`_.

    .. _Java 8’s java.net.URI class: https://docs.oracle.com/javase/8/docs/api/java/net/URI.html
    .. _RFC 2396: https://www.ietf.org/rfc/rfc2396.txt
    .. _RFC 2732: https://www.ietf.org/rfc/rfc2732.txt
    .. _RFC 3986: https://www.ietf.org/rfc/rfc3986.txt

    If a bytes URL is given, it is first converted to `str` using the given
    encoding (which defaults to 'utf-8'). If quote_path is True (default),
    path_encoding ('utf-8' by default) is used to encode URL path component
    which is then quoted. Otherwise, if quote_path is False, path component
    is not encoded or quoted. Given encoding is used for query string
    or form data.

    When passing an encoding, you should use the encoding of the
    original page (the page from which the URL was extracted from).

    Calling this function on an already "safe" URL will return the URL
    unmodified.
    """
    # urlsplit() chokes on bytes input with non-ASCII chars,
    # so let's decode (to Unicode) using page encoding:
    #   - it is assumed that a raw bytes input comes from a document
    #     encoded with the supplied encoding (or UTF8 by default)
    #   - if the supplied (or default) encoding chokes,
    #     percent-encode offending bytes
    decoded = to_unicode(url, encoding=encoding, errors="percentencode")
    parts = urlsplit(_strip(decoded))

    username, password, hostname, port = (
        parts.username,
        parts.password,
        parts.hostname,
        parts.port,
    )
    netloc_bytes = bytearray()
    if username is not None or password is not None:
        if username is not None:
            netloc_bytes += _quote(_unquote(username), _USERINFO_SAFEST_CHARS)
        if password is not None:
            netloc_bytes += b":"
            netloc_bytes += _quote(_unquote(password), _USERINFO_SAFEST_CHARS)
        netloc_bytes += b"@"
    if hostname:
        if ":" in hostname:
            # IPv6 address: urlsplit() strips the brackets from the hostname,
            # but they are required in the netloc when rebuilding the URL.
            netloc_bytes += f"[{hostname}]".encode("ascii")
        else:
            try:
                netloc_bytes += hostname.encode("idna")
            except UnicodeError:
                # IDNA encoding can fail for too long labels (>63 characters) or
                # missing labels (e.g. http://.example.com)
                netloc_bytes += hostname.encode(encoding)
    if port:
        netloc_bytes += b":"
        netloc_bytes += str(port).encode(encoding)

    netloc = netloc_bytes.decode()

    # default encoding for path component SHOULD be UTF-8
    if quote_path:
        path = _quote(parts.path.encode(path_encoding), _PATH_SAFEST_CHARS).decode()
    else:
        path = parts.path

    if parts.scheme in _SPECIAL_SCHEMES:
        query = _quote(
            parts.query.encode(encoding), _SPECIAL_QUERY_SAFEST_CHARS
        ).decode()
    else:
        query = _quote(parts.query.encode(encoding), _QUERY_SAFEST_CHARS).decode()

    return urlunsplit(
        (
            parts.scheme,
            netloc,
            path,
            query,
            _quote(parts.fragment.encode(encoding), _FRAGMENT_SAFEST_CHARS).decode()
            if parts.fragment
            else parts.fragment,
        )
    )


_parent_dirs = re.compile(r"/?(\.\./)+")


def safe_download_url(
    url: str | bytes, encoding: str = "utf8", path_encoding: str = "utf8"
) -> str:
    """Make a url for download. This will call safe_url_string
    and then strip the fragment, if one exists. The path will
    be normalised.

    If the path is outside the document root, it will be changed
    to be within the document root.
    """
    safe_url = safe_url_string(url, encoding, path_encoding)
    scheme, netloc, path, query, _ = urlsplit(safe_url)
    if path:
        path = _parent_dirs.sub("", posixpath.normpath(path))
        if safe_url.endswith("/") and not path.endswith("/"):
            path += "/"
    else:
        path = "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def is_url(text: str) -> bool:
    return text.partition("://")[0] in ("file", "http", "https")


@overload
def url_query_parameter(
    url: str | bytes,
    parameter: str,
    default: None = None,
    keep_blank_values: bool | int = 0,
) -> str | None: ...


@overload
def url_query_parameter(
    url: str | bytes,
    parameter: str,
    default: str,
    keep_blank_values: bool | int = 0,
) -> str: ...


def url_query_parameter(
    url: str | bytes,
    parameter: str,
    default: str | None = None,
    keep_blank_values: bool | int = 0,
) -> str | None:
    """Return the value of a url parameter, given the url and parameter name

    General case:

    >>> import w3lib.url
    >>> w3lib.url.url_query_parameter("product.html?id=200&foo=bar", "id")
    '200'
    >>>

    Return a default value if the parameter is not found:

    >>> w3lib.url.url_query_parameter("product.html?id=200&foo=bar", "notthere", "mydefault")
    'mydefault'
    >>>

    Returns None if `keep_blank_values` not set or 0 (default):

    >>> w3lib.url.url_query_parameter("product.html?id=", "id")
    >>>

    Returns an empty string if `keep_blank_values` set to 1:

    >>> w3lib.url.url_query_parameter("product.html?id=", "id", keep_blank_values=1)
    ''
    >>>

    """

    queryparams = parse_qs(
        urlsplit(str(url))[3], keep_blank_values=bool(keep_blank_values)
    )
    if parameter in queryparams:
        return queryparams[parameter][0]
    return default


def url_query_cleaner(
    url: str | bytes,
    parameterlist: str | bytes | Sequence[str | bytes] = (),
    sep: str = "&",
    kvsep: str = "=",
    remove: bool = False,
    unique: bool = True,
    keep_fragments: bool = False,
) -> str:
    """Clean URL arguments leaving only those passed in the parameterlist keeping order

    >>> import w3lib.url
    >>> w3lib.url.url_query_cleaner("product.html?id=200&foo=bar&name=wired", ('id',))
    'product.html?id=200'
    >>> w3lib.url.url_query_cleaner("product.html?id=200&foo=bar&name=wired", ['id', 'name'])
    'product.html?id=200&name=wired'
    >>>

    If `unique` is ``False``, do not remove duplicated keys

    >>> w3lib.url.url_query_cleaner("product.html?d=1&e=b&d=2&d=3&other=other", ['d'], unique=False)
    'product.html?d=1&d=2&d=3'
    >>>

    If `remove` is ``True``, leave only those **not in parameterlist**.

    >>> w3lib.url.url_query_cleaner("product.html?id=200&foo=bar&name=wired", ['id'], remove=True)
    'product.html?foo=bar&name=wired'
    >>> w3lib.url.url_query_cleaner("product.html?id=2&foo=bar&name=wired", ['id', 'foo'], remove=True)
    'product.html?name=wired'
    >>>

    By default, URL fragments are removed. If you need to preserve fragments,
    pass the ``keep_fragments`` argument as ``True``.

    >>> w3lib.url.url_query_cleaner('http://domain.tld/?bla=123#123123', ['bla'], remove=True, keep_fragments=True)
    'http://domain.tld/#123123'

    """

    if parameterlist and isinstance(parameterlist, (str, bytes)):
        parameterlist = (parameterlist,)

    if isinstance(url, bytes):
        url = url.decode()

    url, _, fragment = url.partition("#")
    base, _, query = url.partition("?")

    if not query or (not parameterlist and not remove):
        return (
            base if not keep_fragments else base + ("#" + fragment if fragment else "")
        )

    param_lookup = set(parameterlist)

    seen: set[str] | None = set() if unique else None
    result: list[str] = []

    for ksv in query.split(sep):
        if not ksv:
            continue

        k, _, _ = ksv.partition(kvsep)

        if seen is not None:
            if k in seen:
                continue
            seen.add(k)

        if remove:
            if k in param_lookup:
                continue
        elif k not in param_lookup:
            continue

        result.append(ksv)

    url = base if not result else base + "?" + sep.join(result)

    if keep_fragments and fragment:
        url += "#" + fragment

    return url


def _add_or_replace_parameters(url: str, params: dict[str, str]) -> str:
    parsed = urlsplit(url)
    current_args = parse_qsl(parsed.query, keep_blank_values=True)

    new_args = []
    seen_params = set()
    for name, value in current_args:
        if name not in params:
            new_args.append((name, value))
        elif name not in seen_params:
            new_args.append((name, params[name]))
            seen_params.add(name)

    not_modified_args = [
        (name, value) for name, value in params.items() if name not in seen_params
    ]
    new_args += not_modified_args

    query = urlencode(new_args)
    return urlunsplit(parsed._replace(query=query))


def add_or_replace_parameter(url: str, name: str, new_value: str) -> str:
    """Add or remove a parameter to a given url

    >>> import w3lib.url
    >>> w3lib.url.add_or_replace_parameter('http://www.example.com/index.php', 'arg', 'v')
    'http://www.example.com/index.php?arg=v'
    >>> w3lib.url.add_or_replace_parameter('http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3', 'arg4', 'v4')
    'http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3&arg4=v4'
    >>> w3lib.url.add_or_replace_parameter('http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3', 'arg3', 'v3new')
    'http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3new'
    >>>

    """
    return _add_or_replace_parameters(url, {name: new_value})


def add_or_replace_parameters(url: str, new_parameters: dict[str, str]) -> str:
    """Add or remove a parameters to a given url

    >>> import w3lib.url
    >>> w3lib.url.add_or_replace_parameters('http://www.example.com/index.php', {'arg': 'v'})
    'http://www.example.com/index.php?arg=v'
    >>> args = {'arg4': 'v4', 'arg3': 'v3new'}
    >>> w3lib.url.add_or_replace_parameters('http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3', args)
    'http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3new&arg4=v4'
    >>>

    """
    return _add_or_replace_parameters(url, new_parameters)


def path_to_file_uri(path: str | os.PathLike[str]) -> str:
    """Convert local filesystem path to legal File URIs as described in:
    http://en.wikipedia.org/wiki/File_URI_scheme
    """
    x = pathname2url(str(Path(path).absolute()))
    return f"file:///{x.lstrip('/')}"


def file_uri_to_path(uri: str) -> str:
    """Convert File URI to local filesystem path according to:
    http://en.wikipedia.org/wiki/File_URI_scheme
    """
    uri_path = _urlparse(uri)[2]
    return url2pathname(uri_path)


def any_to_uri(uri_or_path: str) -> str:
    """If given a path name, return its File URI, otherwise return it
    unmodified
    """
    if os.path.splitdrive(uri_or_path)[0]:
        return path_to_file_uri(uri_or_path)
    u = _urlparse(uri_or_path)
    return uri_or_path if u[0] else path_to_file_uri(uri_or_path)


# ASCII characters.
_char = set(map(chr, range(127)))

# RFC 2045 token.
_token = r"[{}]+".format(
    re.escape(
        "".join(
            _char
            -
            # Control characters.
            set(map(chr, range(32)))
            -
            # tspecials and space.
            set('()<>@,;:\\"/[]?= ')
        )
    )
)

# RFC 822 quoted-string, without surrounding quotation marks.
_quoted_string = r"(?:[{}]|(?:\\[{}]))*".format(
    re.escape("".join(_char - {'"', "\\", "\r"})), re.escape("".join(_char))
)
del _char

# Encode the regular expression strings to make them into bytes, as Python 3
# bytes have no format() method, but bytes must be passed to re.compile() in
# order to make a pattern object that can be used to match on bytes.

# RFC 2397 mediatype.
_mediatype_pattern = re.compile(rf"{_token}/{_token}".encode())
_mediatype_parameter_pattern = re.compile(
    rf';({_token})=(?:({_token})|"({_quoted_string})")'.encode()
)
del _token, _quoted_string


class ParseDataURIResult(NamedTuple):
    """Named tuple returned by :func:`parse_data_uri`."""

    #: MIME type type and subtype, separated by / (e.g. ``"text/plain"``).
    media_type: str
    #: MIME type parameters (e.g. ``{"charset": "US-ASCII"}``).
    media_type_parameters: dict[str, str]
    #: Data, decoded if it was encoded in base64 format.
    data: bytes


def parse_data_uri(uri: str | bytes) -> ParseDataURIResult:
    """Parse a data: URI into :class:`ParseDataURIResult`."""
    if not isinstance(uri, bytes):
        uri = safe_url_string(uri).encode("ascii")

    try:
        scheme, _, uri = uri.partition(b":")
    except ValueError:
        raise ValueError("invalid URI")
    if not scheme or not uri:
        raise ValueError("invalid URI")
    if scheme[:4].lower() != b"data":
        raise ValueError("not a data URI")

    # RFC 3986 section 2.1 allows percent encoding to escape characters that
    # would be interpreted as delimiters, implying that actual delimiters
    # should not be percent-encoded.
    # Decoding before parsing will allow malformed URIs with percent-encoded
    # delimiters, but it makes parsing easier and should not affect
    # well-formed URIs, as the delimiters used in this URI scheme are not
    # allowed, percent-encoded or not, in tokens.
    uri = _unquote(uri)

    media_type = "text/plain"
    media_type_params = {}

    m = _mediatype_pattern.match(uri)
    if m:
        media_type = m.group().decode()
        uri = uri[m.end() :]
    else:
        media_type_params["charset"] = "US-ASCII"

    while True:
        m = _mediatype_parameter_pattern.match(uri)
        if m:
            attribute, value, value_quoted = m.groups()
            if value_quoted:
                value = re.sub(rb"\\(.)", rb"\1", value_quoted)
            media_type_params[attribute.decode()] = value.decode()
            uri = uri[m.end() :]
        else:
            break

    try:
        is_base64, _, data = uri.partition(b",")
    except ValueError:
        raise ValueError("invalid data URI")
    if is_base64:
        if is_base64 != b";base64":
            raise ValueError("invalid data URI")
        data = base64.b64decode(data)

    return ParseDataURIResult(media_type, media_type_params, data)


__all__ = [
    "add_or_replace_parameter",
    "add_or_replace_parameters",
    "any_to_uri",
    "canonicalize_url",
    "file_uri_to_path",
    "is_url",
    "parse_data_uri",
    "path_to_file_uri",
    "safe_download_url",
    "safe_url_string",
    "url_query_cleaner",
    "url_query_parameter",
]


def _urlparse(
    url: str,
    scheme: str = "",
    allow_fragments: bool = True,
) -> tuple[str, str, str, str, str, str]:
    if not url:
        return ParseResult(scheme, "", "", "", "", "")

    i = url.find(":")
    if i > 0:
        scheme_candidate = url[:i]
        if scheme_candidate[0].isalpha():
            scheme = scheme_candidate.lower()
            url = url[i + 1 :]

    netloc = ""
    if url.startswith("//"):
        url = url[2:]
        end = len(url)

        for sep in ("/", "?", "#"):
            j = url.find(sep)
            if j != -1:
                end = min(end, j)

        netloc = url[:end]
        url = url[end:]

    fragment = ""
    if allow_fragments:
        i = url.find("#")
        if i != -1:
            fragment = url[i + 1 :]
            url = url[:i]

    query = ""
    i = url.find("?")
    if i != -1:
        query = url[i + 1 :]
        url = url[:i]

    params = ""
    if scheme in _SPECIAL_SCHEMES:
        i = url.find(";")
        if i != -1:
            params = url[i + 1 :]
            url = url[:i]

    path = url or ""

    return ParseResult(scheme, netloc, path, params, query, fragment)


def _safe_ParseResult(
    parts: ParseResult, encoding: str = "utf8", path_encoding: str = "utf8"
) -> tuple[str, str, str, str, str, str]:
    # IDNA encoding can fail for too long labels (>63 characters)
    # or missing labels (e.g. http://.example.com)
    try:
        netloc = parts.netloc.encode("idna").decode()
    except UnicodeError:
        netloc = parts.netloc

    return (
        parts.scheme,
        netloc,
        _quote(parts.path.encode(path_encoding), _path_safe_chars).decode(),
        _quote(parts.params.encode(path_encoding), _safe_chars).decode(),
        _quote(parts.query.encode(encoding), _safe_chars).decode(),
        _quote(parts.fragment.encode(encoding), _safe_chars).decode(),
    )


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


def canonicalize_url(
    url: str | bytes | ParseResult,
    keep_blank_values: bool = True,
    keep_fragments: bool = False,
    encoding: str | None = None,
) -> str:
    r"""Canonicalize the given url by applying the following procedures:

    - make the URL safe
    - sort query arguments, first by key, then by value
    - normalize all spaces (in query arguments) '+' (plus symbol)
    - normalize percent encodings case (%2f -> %2F)
    - remove query arguments with blank values (unless `keep_blank_values` is True)
    - remove fragments (unless `keep_fragments` is True)

    The url passed can be bytes or unicode, while the url returned is
    always a native str (bytes in Python 2, unicode in Python 3).

    >>> import w3lib.url
    >>>
    >>> # sorting query arguments
    >>> w3lib.url.canonicalize_url('http://www.example.com/do?c=3&b=5&b=2&a=50')
    'http://www.example.com/do?a=50&b=2&b=5&c=3'
    >>>
    >>> # UTF-8 conversion + percent-encoding of non-ASCII characters
    >>> w3lib.url.canonicalize_url('http://www.example.com/r\u00e9sum\u00e9')
    'http://www.example.com/r%C3%A9sum%C3%A9'
    >>>

    For more examples, see the tests in `tests/test_url.py`.
    """
    # If supplied `encoding` is not compatible with all characters in `url`,
    # fallback to UTF-8 as safety net.
    # UTF-8 can handle all Unicode characters,
    # so we should be covered regarding URL normalization,
    # if not for proper URL expected by remote website.
    if isinstance(url, str):
        url = _strip(url)
    try:
        scheme, netloc, path, params, query, fragment = _safe_ParseResult(
            parse_url(url), encoding=encoding or "utf8"
        )
    except UnicodeEncodeError:
        scheme, netloc, path, params, query, fragment = _safe_ParseResult(
            parse_url(url), encoding="utf8"
        )

    # 1. decode query-string as UTF-8 (or keep raw bytes),
    #    sort values,
    #    and percent-encode them back

    # Python's urllib.parse.parse_qsl does not work as wanted
    # for percent-encoded characters that do not match passed encoding,
    # they get lost.
    #
    # e.g., 'q=b%a3' becomes [('q', 'b\ufffd')]
    # (ie. with 'REPLACEMENT CHARACTER' (U+FFFD),
    #      instead of \xa3 that you get with Python2's parse_qsl)
    #
    # what we want here is to keep raw bytes, and percent encode them
    # so as to preserve whatever encoding what originally used.
    #
    # See https://tools.ietf.org/html/rfc3987#section-6.4:
    #
    # For example, it is possible to have a URI reference of
    # "http://www.example.org/r%E9sum%E9.xml#r%C3%A9sum%C3%A9", where the
    # document name is encoded in iso-8859-1 based on server settings, but
    # where the fragment identifier is encoded in UTF-8 according to
    # [XPointer]. The IRI corresponding to the above URI would be (in XML
    # notation)
    # "http://www.example.org/r%E9sum%E9.xml#r&#xE9;sum&#xE9;".
    # Similar considerations apply to query parts.  The functionality of
    # IRIs (namely, to be able to include non-ASCII characters) can only be
    # used if the query part is encoded in UTF-8.
    if query:
        keyvals = parse_qsl_to_bytes(query, keep_blank_values)

        if len(keyvals) > 1:
            keyvals.sort()

        query = urlencode(keyvals)
    else:
        query = ""

    # 2. decode percent-encoded sequences in path as UTF-8 (or keep raw bytes)
    #    and percent-encode path again (this normalizes to upper-case %XX)
    uqp = _unquotepath(path)
    path = _quote(uqp, _path_safe_chars).decode() or "/"

    fragment = "" if not keep_fragments else fragment

    # Apply lowercase to the domain, but not to the userinfo.
    netloc_parts = netloc.split("@")
    netloc_parts[-1] = netloc_parts[-1].lower().rstrip(":")
    netloc = "@".join(netloc_parts)

    # every part should be safe already
    return _urlunparse(scheme, netloc, path, params, query, fragment)


def _unquotepath(path: str) -> bytes:
    for reserved in ("2f", "2F", "3f", "3F"):
        path = path.replace("%" + reserved, "%25" + reserved.upper())

    # standard lib's unquote() does not work for non-UTF-8
    # percent-escaped characters, they get lost.
    # e.g., '%a3' becomes 'REPLACEMENT CHARACTER' (U+FFFD)
    #
    # unquote_to_bytes() returns raw bytes instead
    return _unquote(path)


def parse_url(
    url: str | bytes | ParseResult, encoding: str | None = None
) -> ParseResult:
    """Return urlparsed url from the given argument (which could be an already
    parsed url)
    """
    if isinstance(url, ParseResult):
        return url
    return ParseResult(*_urlparse(to_unicode(url, encoding)))


def parse_qsl_to_bytes(
    qs: str, keep_blank_values: bool = False
) -> list[tuple[bytes, bytes]]:
    """Parse a query given as a string argument.

    Data are returned as a list of name, value pairs as bytes.

    Arguments:

    qs: percent-encoded query string to be parsed

    keep_blank_values: flag indicating whether blank values in
        percent-encoded queries should be treated as blank strings.  A
        true value indicates that blanks should be retained as blank
        strings.  The default false value indicates that blank values
        are to be ignored and treated as if they were  not included.

    """

    if not qs:
        return []

    result: list[tuple[bytes, bytes]] = []

    for name_value in [
        nv for field in qs.split("&") for nv in field.split(";") if field
    ]:
        if "=" in name_value:
            name, _, value = name_value.partition("=")
        else:
            if not keep_blank_values:
                continue
            name, value = name_value, ""

        if value or keep_blank_values:
            # '+' -> space BEFORE decoding
            name_b = _unquote(name.replace("+", " "))
            value_b = _unquote(value.replace("+", " "))

            result.append((name_b, value_b))

    return result
