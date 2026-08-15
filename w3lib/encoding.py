"""
Functions for handling encoding of web pages
"""

from __future__ import annotations

import codecs
import encodings
import re
from re import Match
from typing import TYPE_CHECKING, cast

import w3lib.util

if TYPE_CHECKING:
    from collections.abc import Callable

    from w3lib._types import AnyUnicodeError

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


# Comments are skipped by the WHATWG prescan before it looks for a meta
# charset, so a declaration written inside one is not honored (and a commented
# body tag does not stop the scan). The sibling scanners get_base_url and
# get_meta_refresh strip comments for the same reason; strip them here too.
_COMMENT_STR_RE = re.compile(r"<!--.*?(?:-->|$)", re.DOTALL)
_COMMENT_BYTES_RE = re.compile(rb"<!--.*?(?:-->|$)", re.DOTALL)

# Check for a charset in a meta tag or an xml declaration, and stop the search
# if a body tag is encountered. Any meta tag with a charset counts, however it
# spells its other attributes, e.g. <meta httpequiv="ContentType"
# content="text/html; charset=gbk">.
_BODY_ENCODING_PATTERN = (
    r"""<\s*(?:meta\s+[^>]*?charset\s*=\s*["']?\s*(?P<charset>[\w-]+)"""
    r"""|\?xml\s[^>]+encoding\s*=\s*["']?\s*(?P<xmlcharset>[\w-]+)"""
    r"""|body)"""
)
_BODY_ENCODING_STR_RE = re.compile(_BODY_ENCODING_PATTERN, re.IGNORECASE)
_BODY_ENCODING_BYTES_RE = re.compile(
    _BODY_ENCODING_PATTERN.encode("ascii"), re.IGNORECASE
)


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

    # html5 suggests the first 1024 bytes are sufficient, we allow for more
    chunk = html_body_str[:4096]
    match: Match[bytes] | Match[str] | None
    if isinstance(chunk, bytes):
        match = _BODY_ENCODING_BYTES_RE.search(_COMMENT_BYTES_RE.sub(b"", chunk))
    else:
        match = _BODY_ENCODING_STR_RE.search(_COMMENT_STR_RE.sub("", chunk))

    if match:
        encoding = match.group("charset") or match.group("xmlcharset")
        if encoding:
            return resolve_encoding(w3lib.util.to_unicode(encoding))

    return None


# Default encoding translation
# this maps cannonicalized encodings to target encodings
# see http://www.whatwg.org/specs/web-apps/current-work/multipage/parsing.html#character-encodings-0
# in addition, gb18030 supercedes gb2312 & gbk
# the keys are converted using _c18n_encoding and in sorted order
DEFAULT_ENCODING_TRANSLATION = {
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


def _c18n_encoding(encoding: str) -> str:
    """Canonicalize an encoding name

    This performs normalization and translates aliases using python's
    encoding aliases
    """
    normed = encodings.normalize_encoding(encoding).lower()
    return encodings.aliases.aliases.get(normed, normed)


def resolve_encoding(encoding_alias: str) -> str | None:
    """Return the encoding that `encoding_alias` maps to, or ``None``
    if the encoding cannot be interpreted

    >>> import w3lib.encoding
    >>> w3lib.encoding.resolve_encoding('latin1')
    'cp1252'
    >>> w3lib.encoding.resolve_encoding('gb_2312-80')
    'gb18030'
    >>>

    """
    c18n_encoding = _c18n_encoding(encoding_alias)
    translated = DEFAULT_ENCODING_TRANSLATION.get(c18n_encoding, c18n_encoding)
    try:
        return codecs.lookup(translated).name
    except LookupError:
        return None


_BOM_TABLE = [
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF8, "utf-8"),
]
_FIRST_CHARS = {c[0] for (c, _) in _BOM_TABLE}


def read_bom(data: bytes) -> tuple[None, None] | tuple[str, bytes]:
    r"""Read the byte order mark in the text, if present, and
    return the encoding represented by the BOM and the BOM.

    If no BOM can be detected, ``(None, None)`` is returned.

    >>> import w3lib.encoding
    >>> w3lib.encoding.read_bom(b'\xfe\xff\x6c\x34')
    ('utf-16-be', b'\xfe\xff')
    >>> w3lib.encoding.read_bom(b'\xff\xfe\x34\x6c')
    ('utf-16-le', b'\xff\xfe')
    >>> w3lib.encoding.read_bom(b'\x00\x00\xfe\xff\x00\x00\x6c\x34')
    ('utf-32-be', b'\x00\x00\xfe\xff')
    >>> w3lib.encoding.read_bom(b'\xff\xfe\x00\x00\x34\x6c\x00\x00')
    ('utf-32-le', b'\xff\xfe\x00\x00')
    >>> w3lib.encoding.read_bom(b'\x01\x02\x03\x04')
    (None, None)
    >>>

    """

    # common case is no BOM, so this is fast
    if data and data[0] in _FIRST_CHARS:
        for bom, encoding in _BOM_TABLE:
            if data.startswith(bom):
                return encoding, bom
    return None, None


# Python decoder doesn't follow unicode standard when handling
# bad utf-8 encoded strings. see http://bugs.python.org/issue8271
codecs.register_error(
    "w3lib_replace", lambda exc: ("\ufffd", cast("AnyUnicodeError", exc).end)
)


def _gb18030_replace(exc: UnicodeError) -> tuple[str, int]:
    error = cast("AnyUnicodeError", exc)
    if error.object[error.start] == 0x80:
        return "\u20ac", error.start + 1
    return "\ufffd", error.end


# The GB18030 decoder of the Encoding Standard decodes a lead 0x80 as the euro
# sign, for GBK compatibility, while the Python codec rejects it.
# https://encoding.spec.whatwg.org/#gb18030-decoder
codecs.register_error("w3lib_gb18030_replace", _gb18030_replace)


def to_unicode(data_str: bytes, encoding: str) -> str:
    r"""Convert a str object to unicode using the encoding given

    Characters that cannot be converted will be converted to ``\ufffd`` (the
    unicode replacement character).
    """
    # Every name that resolves to gb18030 contains "18030", so the substring
    # check keeps the codec lookup out of the common case.
    errors = (
        "w3lib_gb18030_replace"
        if "18030" in encoding and codecs.lookup(encoding).name == "gb18030"
        else "replace"
    )
    return data_str.decode(encoding, errors)


def html_to_unicode(
    content_type_header: str | None,
    html_body_str: bytes,
    default_encoding: str = "utf8",
    auto_detect_fun: Callable[[bytes], str | None] | None = None,
) -> tuple[str, str]:
    r'''Convert raw html bytes to unicode

    This attempts to make a reasonable guess at the content encoding of the
    html body, following a similar process to a web browser.

    It will try in order:

    * BOM (byte-order mark)
    * http content type header
    * meta or xml tag declarations
    * auto-detection, if the `auto_detect_fun` keyword argument is not ``None``
    * default encoding in keyword arg (which defaults to utf8)

    If an encoding other than the auto-detected or default encoding is used,
    overrides will be applied, converting some character encodings to more
    suitable alternatives.

    If a BOM is found matching the encoding, it will be stripped.

    The `auto_detect_fun` argument can be used to pass a function that will
    sniff the encoding of the text. This function must take the raw text as an
    argument and return the name of an encoding that python can process, or
    None.  To use chardet, for example, you can define the function as::

        auto_detect_fun=lambda x: chardet.detect(x).get('encoding')

    or to use UnicodeDammit (shipped with the BeautifulSoup library)::

        auto_detect_fun=lambda x: UnicodeDammit(x).originalEncoding

    If the locale of the website or user language preference is known, then a
    better default encoding can be supplied.

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
    bom_enc, bom = read_bom(html_body_str)
    if bom_enc is not None and bom is not None:
        return bom_enc, to_unicode(html_body_str[len(bom) :], bom_enc)

    enc = http_content_type_encoding(content_type_header)
    if enc is not None:
        if enc in {"utf-16", "utf-32"}:
            enc += "-be"
        return enc, to_unicode(html_body_str, enc)
    enc = html_body_declared_encoding(html_body_str)
    if enc is None and (auto_detect_fun is not None):
        enc = auto_detect_fun(html_body_str)
    if enc is None:
        enc = default_encoding
    return enc, to_unicode(html_body_str, enc)
