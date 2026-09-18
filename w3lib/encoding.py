"""
Functions for handling encoding of web pages
"""

from __future__ import annotations

import codecs
import encodings
import re
from functools import cached_property, lru_cache
from typing import TYPE_CHECKING, Protocol, cast

from w3lib._util import _ascii_compatible, iter_tag_attributes

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


# Scan for the first meta tag or xml declaration, and stop the search if a
# body tag is encountered.
# Comments are skipped by the WHATWG prescan before it looks for a meta
# charset, so a declaration written inside one is not honored (and a commented
# body tag does not stop the scan): they are consumed as an alternative of the
# scan itself, as get_base_url() does, rather than stripped out beforehand, so
# the text on either side of a comment is never spliced into a tag.
# A meta tag is consumed with its quoted attribute values whole, so a quoted
# ">" does not end it and a quoted "<!--" does not start a comment.
# Each alternative consumes every character at most once, so the scan stays
# linear.
_BODY_SCAN_RE = re.compile(
    r"""
      <!--.*?(?:-->|$)  # comment
    | <\s*meta(?=[\s/])(?P<meta>(?:[^<>=]|=\s*(?:"[^"]*"|'[^']*')?)*)  # meta tag
    | <\?xml\s(?P<xml>[^<>]*)  # XML declaration
    | <\s*(?P<body>body)  # start of the body tag
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)
# The pragma attribute, however spelled (e.g. #155 has httpequiv="ContentType").
_HTTP_EQUIV_NAMES = frozenset({"http-equiv", "http_equiv", "httpequiv"})
# Its value must name the content-type pragma, also however spelled.
_CONTENT_TYPE_PRAGMA_RE = re.compile(r"content[-_ ]?type", re.IGNORECASE)
# A "charset=" wherever it occurs in a content attribute value, as in the
# WHATWG "extract a character encoding from a meta element" algorithm.
_CONTENT_CHARSET_RE = re.compile(
    r"""charset\s*=\s*["']?\s*(?P<label>[\w-]+)""", re.IGNORECASE
)


def _leading_label(value: str) -> str | None:
    match = _ENCODING_LABEL_RE.match(value.lstrip())
    return match.group() if match else None


def _meta_charset_label(attrs: str) -> str | None:
    """Return the encoding label the meta tag with attribute text `attrs`
    declares, or ``None``.

    The WHATWG prescan only honors a real charset attribute, or a "charset="
    inside a content attribute value when the tag also carries the
    http-equiv=content-type pragma. Both the name and the value of that pragma
    are matched loosely.
    """
    has_pragma = False
    content_label = None
    for name, value in iter_tag_attributes(attrs):
        if name == "charset":
            if label := _leading_label(value):
                return label
        elif name == "content":
            if content_label is None and (match := _CONTENT_CHARSET_RE.search(value)):
                content_label = match.group("label")
        elif name in _HTTP_EQUIV_NAMES and _CONTENT_TYPE_PRAGMA_RE.search(value):
            has_pragma = True
    return content_label if has_pragma else None


def _xml_encoding_label(attrs: str) -> str | None:
    for name, value in iter_tag_attributes(attrs):
        if name == "encoding" and (label := _leading_label(value)):
            return label
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

    # html5 suggests the first 1024 bytes are sufficient, we allow for more
    chunk = html_body_str[:4096]
    if isinstance(chunk, bytes):
        # A declaration is ASCII markup and an encoding label is ASCII text.
        chunk = chunk.decode("latin-1")
    for match in _BODY_SCAN_RE.finditer(chunk):
        if match.group("body") is not None:
            break
        if (attrs := match.group("meta")) is not None:
            # A meta tag can only declare an encoding by spelling "charset",
            # as an attribute name or inside a content attribute value, so the
            # tags that cannot need no attribute walk.
            if "charset" not in attrs.lower():
                continue
            label = _meta_charset_label(attrs)
        elif match.group("xml") is not None:
            label = _xml_encoding_label(match.group("xml"))
        else:  # a comment
            continue
        if label is not None:
            return resolve_encoding(label)

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


@lru_cache(maxsize=256)
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
        name = codecs.lookup(translated).name
    except LookupError:
        return None
    # UTF-7 has no label in the WHATWG Encoding Standard this module follows and
    # browsers dropped it. It re-spells "<", ">" and "&" using only ASCII bytes
    # (e.g. "+ADw-" for "<"), so a response that declares charset=utf-7 lets a
    # byte sequence a browser shows as inert text decode into live markup. Refuse
    # it so callers fall back to a safe default instead of the smuggled encoding.
    if name == "utf-7":
        return None
    return name


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


class EncodingDecision(Protocol):
    """Encoding that an :class:`EncodingBackend` chose for a document.

    .. versionadded:: VERSION
    """

    @property
    def name(self) -> str:
        """Name of the encoding, as the backend spells it."""

    @property
    def ascii_compatible(self) -> bool:
        """Whether ASCII bytes decode to the same ASCII characters."""

    def decode(self, body: bytes) -> str:
        """Decode *body*."""


class EncodingBackend(Protocol):
    """Policy that chooses and decodes the encoding of a document.

    .. versionadded:: VERSION

    :class:`DefaultEncodingBackend` follows the WHATWG detection rules with
    Python codecs. Another implementation can plug in a different detection
    or decoder, and since the same decision names the encoding and decodes
    the text, both always agree.

    *policy_id* names the policy, so that data recorded under one policy
    can be told apart from data recorded under another.
    """

    policy_id: str

    def resolve(
        self,
        body: bytes,
        content_type: str = "",
        encoding: str | None = None,
    ) -> EncodingDecision:
        """Choose the encoding of *body*.

        *content_type* is the value of the Content-Type header, and *encoding*
        is an encoding label that the caller asks for explicitly.
        """


class EncodingContext:
    """Encoding of a document, resolved and decoded lazily.

    .. versionadded:: VERSION

    *body*, *content_type* and *encoding* are the arguments that
    :meth:`EncodingBackend.resolve` gets, on first access to
    :attr:`decision`, :attr:`encoding`, :attr:`text` or
    :attr:`request_encoding`. Nothing is decoded until :attr:`text` is read.
    """

    def __init__(
        self,
        body: bytes,
        content_type: str = "",
        *,
        backend: EncodingBackend,
        encoding: str | None = None,
    ):
        self.body: bytes = body
        self.content_type: str = content_type
        self.backend: EncodingBackend = backend
        self.explicit_encoding: str | None = encoding

    @cached_property
    def decision(self) -> EncodingDecision:
        """Encoding chosen by the backend."""
        return self.backend.resolve(
            self.body, self.content_type, self.explicit_encoding
        )

    @property
    def encoding(self) -> str:
        """Name of the encoding chosen by the backend."""
        return self.decision.name

    @cached_property
    def text(self) -> str:
        """The whole body decoded."""
        return self.decision.decode(self.body)

    @property
    def request_encoding(self) -> str:
        """Encoding for URLs found in the document, in the Python spelling.

        It is UTF-8 when the document encoding is not ASCII-compatible or
        Python has no codec for it.
        """
        if not self.decision.ascii_compatible:
            return "utf-8"
        try:
            codecs.lookup(self.encoding)
        except LookupError:
            return "utf-8"
        return self.encoding


class _Decision:
    def __init__(self, name: str, bom: bytes = b""):
        self.name = name
        self._bom = bom

    @property
    def ascii_compatible(self) -> bool:
        return _ascii_compatible(self.name)

    def decode(self, body: bytes) -> str:
        return to_unicode(body.removeprefix(self._bom), self.name)


class DefaultEncodingBackend:
    """:class:`EncodingBackend` built on the functions of this module.

    .. versionadded:: VERSION

    It chooses the encoding the way :func:`html_to_unicode` does, and
    decodes with Python codecs the way :func:`to_unicode` does.
    *default_encoding* is the fallback, and *auto_detect_func* sniffs the
    encoding before falling back to it, as the same parameters of
    :func:`html_to_unicode` do. An *encoding* passed to :meth:`resolve` only
    yields to a byte order mark.
    """

    policy_id = "w3lib"

    def __init__(
        self,
        default_encoding: str = "utf8",
        auto_detect_func: Callable[[bytes], str | None] | None = None,
    ):
        self._default_encoding = default_encoding
        self._auto_detect_func = auto_detect_func

    def resolve(
        self,
        body: bytes,
        content_type: str = "",
        encoding: str | None = None,
    ) -> EncodingDecision:
        """Choose the encoding of *body*."""
        return _Decision(
            *_resolve(
                body,
                content_type,
                encoding,
                self._default_encoding,
                self._auto_detect_func,
            )
        )


def _resolve(
    body: bytes,
    content_type: str | None,
    encoding: str | None,
    default_encoding: str,
    auto_detect_func: Callable[[bytes], str | None] | None,
) -> tuple[str, bytes]:
    bom_enc, bom = read_bom(body)
    if bom_enc is not None and bom is not None:
        return bom_enc, bom
    enc = (
        (resolve_encoding(encoding) if encoding else None)
        or http_content_type_encoding(content_type)
        or html_body_declared_encoding(body)
    )
    if enc is None and auto_detect_func is not None:
        enc = auto_detect_func(body)
    if enc is None:
        enc = default_encoding
    elif enc in {"utf-16", "utf-32"}:
        enc += "-be"
    return enc, b""


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
    enc, bom = _resolve(
        html_body_str, content_type_header, None, default_encoding, auto_detect_fun
    )
    return enc, to_unicode(html_body_str[len(bom) :], enc)
