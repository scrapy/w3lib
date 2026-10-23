"""
Functions for handling encoding of web pages
"""

from __future__ import annotations

import re
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from frostwork.encoding import (
    bom_encoding,
    codec_name,
    declared_encoding,
    decode,
    detect_encoding,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# The value ends at whitespace, ";", "," or the end of the header. Comma is
# not parameter syntax; stopping the value at "," approximates Fetch's
# "extract a MIME type" for comma-joined duplicate headers, keeping the first
# charset rather than the last valid MIME type's.
_HEADER_ENCODING_RE = re.compile(
    r"(?:^|;)[ \t]*charset="
    r'(?:"([\w-]+)"|([\w-]+))'
    r"(?![^\s;,])",
    re.IGNORECASE,
)
# https://mimesniff.spec.whatwg.org/commit-snapshots/39aa53511b13953d84fef8d4131d6f61d0ccbde6/#parse-a-mime-type
# Parameters are ";"-separated name=value pairs whose value is either a token
# or a quoted-string, and a quoted-string is opaque
# (https://fetch.spec.whatwg.org/commit-snapshots/586cd2a44c2a865b37c166dc0740f3fb8bb220d6/#collect-an-http-quoted-string),
# so it has to be consumed as a whole: a "charset=" written inside one belongs
# to that value and is not a parameter of its own.
_HEADER_PARAMETER_RE = re.compile(
    r"(?:^|;)[ \t]*(?P<name>[^\s;=]+)="
    r'(?:"(?P<quoted>[^"\\]*(?:\\.[^"\\]*)*)"(?![^\s;,])'
    r"|(?P<token>[^;,\s]*))"
)
_ENCODING_LABEL_RE = re.compile(r"[\w-]+")


def _quoted_aware_charset(content_type: str) -> str | None:
    for match in _HEADER_PARAMETER_RE.finditer(content_type):
        if match.group("name").lower() != "charset":
            continue
        label = match.group("quoted")
        if label is None:
            label = match.group("token")
        if _ENCODING_LABEL_RE.fullmatch(label):
            return resolve_encoding(label)
    return None


def http_content_type_encoding(content_type: str | None) -> str | None:
    """Extract the encoding in the content-type header

    >>> import w3lib.encoding
    >>> w3lib.encoding.http_content_type_encoding("Content-Type: text/html; charset=ISO-8859-4")
    'iso8859-4'

    """

    if content_type:
        match = _HEADER_ENCODING_RE.search(content_type)
        if match:
            # A match inside a quoted-string must be preceded by that string's
            # opening quote, so if no '"' precedes it the fast answer is
            # correct; only otherwise walk the parameters.
            if content_type.find('"', 0, match.start()) < 0:
                return resolve_encoding(match.group(1) or match.group(2))
            return _quoted_aware_charset(content_type)

    return None


def html_body_declared_encoding(html_body_str: str | bytes) -> str | None:
    '''Return the encoding specified in meta tags in the html body,
    or ``None`` if no suitable encoding was found

    >>> import w3lib.encoding
    >>> w3lib.encoding.html_body_declared_encoding(
    ... """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    ...      "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
    ... <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
    ... <head>
    ...     <title>Some title</title>
    ...     <meta http-equiv="content-type" content="text/html;charset=utf-8" />
    ... </head>
    ... <body>
    ... ...
    ... </body>
    ... </html>""")
    'utf-8'
    >>>

    '''

    if isinstance(html_body_str, str):
        html_body_str = html_body_str.encode("utf-8", "replace")
    name = declared_encoding(html_body_str)
    return None if name is None else codec_name(name)


_DEPRECATED_ENCODING_TRANSLATION = {
    "ascii": "cp1252",
    "big5": "big5hkscs",
    "euc_kr": "cp949",
    "gb2312": "gb18030",
    "gb_2312_80": "gb18030",
    "gbk": "gb18030",
    "iso8859_11": "cp874",
    "iso8859_9": "cp1254",
    "latin_1": "cp1252",
    "macintosh": "mac_roman",
    "shift_jis": "cp932",
    "tis_620": "cp874",
    "win_1251": "cp1251",
    "windows_31j": "cp932",
    "win_31j": "cp932",
    "windows_874": "cp874",
    "win_874": "cp874",
    "x_sjis": "cp932",
    "zh_cn": "gb18030",
}


def __getattr__(name: str) -> Any:
    if name == "DEFAULT_ENCODING_TRANSLATION":
        warnings.warn(
            "w3lib.encoding.DEFAULT_ENCODING_TRANSLATION is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _DEPRECATED_ENCODING_TRANSLATION
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@lru_cache(maxsize=256)
def resolve_encoding(encoding_alias: str) -> str | None:
    """Return the Python codec name of the encoding of the `Encoding
    Standard`_ that `encoding_alias` maps to, or ``None`` if there is none,
    e.g. for ``utf-32``.

    .. _Encoding Standard: https://encoding.spec.whatwg.org/

    >>> import w3lib.encoding
    >>> w3lib.encoding.resolve_encoding('latin1')
    'cp1252'
    >>> w3lib.encoding.resolve_encoding('gb_2312-80')
    'gbk'
    >>> w3lib.encoding.resolve_encoding('base64')
    >>>

    """
    return codec_name(encoding_alias)


def read_bom(data: bytes) -> tuple[None, None] | tuple[str, bytes]:
    r"""Read the byte order mark in the text, if present, and
    return the encoding represented by the BOM and the BOM.

    If no BOM can be detected, ``(None, None)`` is returned.

    As in browsers, a UTF-32LE BOM reads as a UTF-16LE one, and a UTF-16 body
    that starts with an XML declaration and no BOM gives an empty BOM.

    >>> import w3lib.encoding
    >>> w3lib.encoding.read_bom(b'\xfe\xff\x6c\x34')
    ('utf-16-be', b'\xfe\xff')
    >>> w3lib.encoding.read_bom(b'\xff\xfe\x34\x6c')
    ('utf-16-le', b'\xff\xfe')
    >>> w3lib.encoding.read_bom(b'\x01\x02\x03\x04')
    (None, None)
    >>>

    """
    bom = bom_encoding(data)
    if bom is None:
        return None, None
    name, length = bom
    return cast("str", codec_name(name)), data[:length]


def to_unicode(data_str: bytes, encoding: str) -> str:
    r"""Convert a str object to unicode using the encoding given

    If *encoding* names an encoding of the `Encoding Standard`_, *data_str* is
    decoded the way browsers decode it, e.g. ``utf-16`` is UTF-16LE.

    Characters that cannot be converted will be converted to ``\ufffd`` (the
    unicode replacement character).

    .. _Encoding Standard: https://encoding.spec.whatwg.org/
    """
    try:
        return decode(data_str, encoding)
    except LookupError:
        return data_str.decode(encoding, "replace")


def html_encoding(content_type_header: str | None, html_body_str: bytes) -> str:
    """Return the encoding :func:`html_to_unicode` would decode
    *html_body_str* with, without decoding it.

    .. versionadded:: VERSION

    >>> import w3lib.encoding
    >>> w3lib.encoding.html_encoding(None, b'<meta charset="latin1">')
    'cp1252'
    """
    enc = http_content_type_encoding(content_type_header)
    return cast("str", codec_name(detect_encoding(html_body_str, enc)))


def html_to_unicode(
    content_type_header: str | None,
    html_body_str: bytes,
    default_encoding: str | None = None,
    auto_detect_fun: Callable[[bytes], str | None] | None = None,
) -> tuple[str, str]:
    r'''Convert raw html bytes to unicode

    This finds the encoding of the html body the way a web browser does,
    trying in order:

    * BOM (byte-order mark)
    * http content type header
    * meta or xml tag declarations
    * UTF-8, if the body is valid UTF-8
    * the encoding guessed from the bytes of the body, as Firefox does

    If a BOM is found, it will be stripped.

    If `content_type_header` is not present, ``None`` can be passed signifying
    that the header was not present.

    This method will not fail, if characters cannot be converted to unicode,
    ``\ufffd`` (the unicode replacement character) will be inserted instead.

    Returns a tuple of ``(<encoding used>, <unicode_string>)``

    Examples:

    >>> import w3lib.encoding
    >>> w3lib.encoding.html_to_unicode(None,
    ... b"""<!DOCTYPE html>
    ... <head>
    ... <meta charset="UTF-8" />
    ... <meta name="viewport" content="width=device-width" />
    ... <title>Creative Commons France</title>
    ... <link rel='canonical' href='http://creativecommons.fr/' />
    ... <body>
    ... <p>Creative Commons est une organisation \xc3\xa0 but non lucratif
    ... qui a pour dessein de faciliter la diffusion et le partage des oeuvres
    ... tout en accompagnant les nouvelles pratiques de cr\xc3\xa9ation \xc3\xa0 l\xe2\x80\x99\xc3\xa8re numerique.</p>
    ... </body>
    ... </html>""")
    ('utf-8', '<!DOCTYPE html>\n<head>\n<meta charset="UTF-8" />\n<meta name="viewport" content="width=device-width" />\n<title>Creative Commons France</title>\n<link rel=\'canonical\' href=\'http://creativecommons.fr/\' />\n<body>\n<p>Creative Commons est une organisation \xe0 but non lucratif\nqui a pour dessein de faciliter la diffusion et le partage des oeuvres\ntout en accompagnant les nouvelles pratiques de cr\xe9ation \xe0 l\u2019\xe8re numerique.</p>\n</body>\n</html>')
    >>>

    '''
    bom = bom_encoding(html_body_str)
    if bom is not None:
        name, length = bom
        return cast("str", codec_name(name)), decode(html_body_str[length:], name)
    enc = http_content_type_encoding(content_type_header)
    if auto_detect_fun is None and default_encoding is None:
        name = detect_encoding(html_body_str, enc)
        return cast("str", codec_name(name)), decode(html_body_str, name)
    warnings.warn(
        "The default_encoding and auto_detect_fun parameters of "
        "w3lib.encoding.html_to_unicode() are deprecated.",
        DeprecationWarning,
        stacklevel=2,
    )
    if enc is None:
        enc = html_body_declared_encoding(html_body_str)
    if enc is None and auto_detect_fun is not None:
        enc = auto_detect_fun(html_body_str)
    if enc is None:
        enc = default_encoding or "utf8"
    return enc, to_unicode(html_body_str, enc)
