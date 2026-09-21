"""
Functions for dealing with markup text
"""

from __future__ import annotations

import functools
import re
from html.entities import name2codepoint
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from w3lib._util import _scannable, iter_tag_attributes, to_unicode
from w3lib.url import safe_url_string

if TYPE_CHECKING:
    from collections.abc import Iterable


# Character references are ASCII digits only; \d would also match the Unicode
# decimal digits, which int() accepts but no HTML parser decodes.
_ent_re = re.compile(
    r"&((?P<named>[a-z0-9]+)|#(?P<dec>[0-9]+)|#x(?P<hex>[a-f0-9]+))(?P<semicolon>;?)",
    re.IGNORECASE,
)
# The text of a tag after its name, up to the angle bracket that ends the tag.
# A quoted attribute value is consumed whole, so that an angle bracket in it
# does not end the tag. A quote opens a value only right after the "=" of an
# attribute; anywhere else in a tag, HTML parsers take it as part of a name or
# of an unquoted value, and the tag still ends at the first ">". The runs of
# other characters stop at every "=", and what follows one is a double-quoted
# value, a single-quoted value or neither, which gives a tag body a single
# parse and hence nothing to backtrack into.
_TAG_BODY = r"""[^<>=]*(?:(?:=\s*"[^"]*"|=\s*'[^']*'|=(?!\s*["']))[^<>=]*)*"""
# Only a tag named the way an HTML element is gets its body read that way.
# Pairing quotes across a "<" that opens no tag, e.g. the one in "i<n" inside a
# script, would take the tag to the far side of the next quote, and past every
# tag in between. A name is pinned to its full length, as below, so that the
# "<" of "n<arguments.length" is left to the plain reading.
_TAG_NAME = r"""[a-zA-Z][a-zA-Z0-9]*(?![^ <>/])"""
# Anything else, a markup declaration or a tag named otherwise, keeps the plain
# reading: an apostrophe in a comment is text, and pairing it with a later
# quote would swallow the markup in between.
_tag_re = re.compile(rf"""</?{_TAG_NAME}{_TAG_BODY}>|<[a-zA-Z/!][^<>]*>""")
# Tag syntax is ASCII, and re.ASCII holds the scan patterns of this module to
# it: "\s" matches the whitespace that separates markup and not, say, U+3000,
# and case-insensitive matching pairs no "s" with "\u017f" nor "k" with
# "\u212a". It is also what makes a pattern and its byte counterpart match the
# same markup.
_base_re = re.compile("<base", re.IGNORECASE | re.ASCII)
_base_bytes_re = re.compile(rb"<base", re.IGNORECASE)
# Scan for the first honored <base href>, consuming comments and
# <script>/<noscript> content (where a browser never parses tags) along the
# way. Ignorable regions come first in the alternation, so a <base> inside one
# is consumed before it can match; unterminated regions swallow the rest of
# the document, as a browser does. Their content is consumed in runs of
# characters that cannot start the closing delimiter, so that the large inline
# scripts of real pages cost a tight loop per run rather than a match attempt
# per character.
_base_scan_re = re.compile(
    r"""
      <!--[^-]*(?:-(?!->)[^-]*)*(?:-->|$)
    | <(?P<t>script|noscript)\b[^<>]*>[^<]*(?:<(?!/(?P=t)>)[^<]*)*(?:</(?P=t)>|$)
    | <base\s[^<>]*href\s*=\s*["']\s*(?P<url>[^"'\s]+)\s*["']
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE | re.ASCII,
)


# The refresh payload: ``3; url=...``. The url= part is required.
# The interval is ASCII digits only, as in the HTML refresh steps.
_meta_refresh_content_re = re.compile(
    r"\s*(?P<int>([0-9]*\.)?[0-9]+)\s*;\s*url=\s*(?P<url>.*)",
    re.DOTALL | re.IGNORECASE,
)

_CDATA_START = "<![CDATA["
_CDATA_END = "]]>"
_tags_re = re.compile(
    rf"""
      </?(?P<named>{_TAG_NAME})
                    # a tag named the way an HTML element is, whose quoted
      {_TAG_BODY}>  # attribute values are read whole
    |
    </?             # opening angle bracket, optional slash for a closing tag
    (?P<name>[^ <>/]+)
                    # tag name (captured): a run of non-space, non-bracket chars,
    (?![^ <>/])     # pinned to its maximal length by this lookahead so it can't
                    # overlap the run below and backtrack quadratically on an
                    # unterminated tag (a "<" with a long run and no ">")
    [^<>]*          # the rest of the tag: attributes, whitespace, etc.
    >               # closing angle bracket
    """,
    re.IGNORECASE | re.VERBOSE,
)
_meta_re = re.compile("<meta", re.IGNORECASE | re.ASCII)


def _meta_scan_source(ignore_tags: tuple[str, ...]) -> str:
    # Scan for <meta> tags, consuming comments and the content of the ignored
    # tags along the way. Ignorable regions come first in the alternation, so a
    # <meta> inside one is consumed before it can match; unterminated regions
    # swallow the rest of the document, as a browser does. Their content is
    # consumed in runs of characters that cannot start the closing delimiter,
    # so that the large inline scripts of real pages cost a tight loop per run
    # rather than a match attempt per character. The end tag closes on the tag
    # name followed by whitespace, "/" or ">", as browsers treat it.
    #
    # The <meta> body is matched without the closing angle bracket, which is
    # not required: a tag left unterminated by the next "<" or by the end of
    # the text is still parsed, as browsers do.
    alternatives = [r"<!--[^-]*(?:-(?!->)[^-]*)*(?:-->|$)"]
    if ignore_tags:
        tags = "|".join(re.escape(tag) for tag in ignore_tags)
        alternatives.append(
            rf"<(?P<t>{tags})\b[^<>]*>[^<]*(?:<(?!/(?P=t)[\s/>])[^<]*)*"
            r"(?:</(?P=t)[^<>]*>?|$)"
        )
    alternatives.append(r"<meta\s(?P<attrs>[^<>]*)")
    return "|".join(alternatives)


@functools.lru_cache(maxsize=256)
def _build_meta_scan_pattern(ignore_tags: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(_meta_scan_source(ignore_tags), re.IGNORECASE | re.ASCII)


@functools.lru_cache(maxsize=256)
def _build_meta_scan_bytes_pattern(ignore_tags: tuple[str, ...]) -> re.Pattern[bytes]:
    return re.compile(_meta_scan_source(ignore_tags).encode(), re.IGNORECASE)


HTML5_WHITESPACE = " \t\n\r\x0c"


def replace_entities(
    text: str | bytes,
    keep: Iterable[str] = (),
    remove_illegal: bool = True,
    encoding: str = "utf-8",
) -> str:
    r"""Remove entities from the given `text` by converting them to their
    corresponding unicode character.

    `text` can be a unicode string or a byte string encoded in the given
    `encoding` (which defaults to 'utf-8').

    If `keep` is passed (with a list of entity names) those entities will
    be kept (they won't be removed).

    It supports both numeric entities (``&#nnnn;`` and ``&#hhhh;``)
    and named entities (such as ``&nbsp;`` or ``&gt;``).

    If `remove_illegal` is ``True``, entities that can't be converted are removed.
    If `remove_illegal` is ``False``, entities that can't be converted are kept "as
    is". For more information see the tests.

    Always returns a unicode string (with the entities removed).

    >>> import w3lib.html
    >>> w3lib.html.replace_entities(b'Price: &pound;100')
    'Price: \xa3100'
    >>> print(w3lib.html.replace_entities(b'Price: &pound;100'))
    Price: £100
    >>>

    """

    def convert_entity(m: re.Match[str]) -> str:
        groups = m.groupdict()
        number = None
        if groups.get("dec"):
            number = int(groups["dec"], 10)
        elif groups.get("hex"):
            number = int(groups["hex"], 16)
        else:
            # guaranteed to be named
            entity_name = groups["named"]
            if entity_name.lower() in keep:
                return m.group(0)
            number = name2codepoint.get(entity_name) or name2codepoint.get(
                entity_name.lower()
            )
        if number is not None:
            # A null or surrogate reference is a parse error that the tokenizer
            # resolves to U+FFFD; chr() would instead emit a NUL or a lone
            # surrogate, which is not a Unicode scalar value and fails to
            # encode. Out-of-range references keep the remove_illegal handling.
            # https://html.spec.whatwg.org/commit-snapshots/3e7b72c44ce144cee7db859cd0647af6646b6793/#numeric-character-reference-end-state
            if number == 0 or 0xD800 <= number <= 0xDFFF:
                return "\ufffd"
            # Numeric character references in the 80-9F range are typically
            # interpreted by browsers as representing the characters mapped
            # to bytes 80-9F in the Windows-1252 encoding. For more info
            # see: http://en.wikipedia.org/wiki/Character_encodings_in_HTML
            try:
                if 0x80 <= number <= 0x9F:
                    return bytes((number,)).decode("cp1252")
                return chr(number)
            except (ValueError, OverflowError):
                pass

        return "" if remove_illegal and groups.get("semicolon") else m.group(0)

    return _ent_re.sub(convert_entity, to_unicode(text, encoding))


def has_entities(text: str | bytes, encoding: str | None = None) -> bool:
    return bool(_ent_re.search(to_unicode(text, encoding)))


def replace_tags(
    text: str | bytes, token: str = "", encoding: str | None = None
) -> str:
    r"""Replace all markup tags found in the given `text` by the given token.
    By default `token` is an empty string so it just removes all tags.

    `text` can be a unicode string or a regular string encoded as `encoding`
    (or ``'utf-8'`` if `encoding` is not given.)

    Always returns a unicode string.

    Examples:

    >>> import w3lib.html
    >>> w3lib.html.replace_tags('This text contains <a>some tag</a>')
    'This text contains some tag'
    >>> w3lib.html.replace_tags('<p>Je ne parle pas <b>fran\xe7ais</b></p>', ' -- ', 'latin-1')
    ' -- Je ne parle pas  -- fran\xe7ais --  -- '
    >>>

    """

    return _tag_re.sub(token, to_unicode(text, encoding))


_REMOVECOMMENTS_RE = re.compile("<!--.*?(?:-->|$)", re.DOTALL)


def remove_comments(text: str | bytes, encoding: str | None = None) -> str:
    """Remove HTML Comments.

    >>> import w3lib.html
    >>> w3lib.html.remove_comments(b"test <!--textcoment--> whatever")
    'test  whatever'
    >>>

    """

    utext = to_unicode(text, encoding)
    return _REMOVECOMMENTS_RE.sub("", utext)


def _remove_tag(
    m: re.Match[str], which_ones: set[str] | tuple[()], keep: set[str] | tuple[()]
) -> str:
    tag = (m.group("named") or m.group("name")).lower()

    should_remove = tag in which_ones if which_ones else tag not in keep

    return "" if should_remove else m.group(0)


def remove_tags(
    text: str | bytes,
    which_ones: Iterable[str] = (),
    keep: Iterable[str] = (),
    encoding: str | None = None,
) -> str:
    """Remove HTML Tags only.

    `which_ones` and `keep` are both tuples, there are four cases:

    ==============  ============= ==========================================
    ``which_ones``  ``keep``      what it does
    ==============  ============= ==========================================
    **not empty**   empty         remove all tags in ``which_ones``
    empty           **not empty** remove all tags except the ones in ``keep``
    empty           empty         remove all tags
    **not empty**   **not empty** not allowed
    ==============  ============= ==========================================


    Remove all tags:

    >>> import w3lib.html
    >>> doc = '<div><p><b>This is a link:</b> <a href="http://www.example.com">example</a></p></div>'
    >>> w3lib.html.remove_tags(doc)
    'This is a link: example'
    >>>

    Keep only some tags:

    >>> w3lib.html.remove_tags(doc, keep=('div',))
    '<div>This is a link: example</div>'
    >>>

    Remove only specific tags:

    >>> w3lib.html.remove_tags(doc, which_ones=('a','b'))
    '<div><p>This is a link: example</p></div>'
    >>>

    You can't remove some and keep some:

    >>> w3lib.html.remove_tags(doc, which_ones=('a',), keep=('p',))
    Traceback (most recent call last):
        ...
    ValueError: Cannot use both which_ones and keep
    >>>

    """
    if which_ones and keep:
        raise ValueError("Cannot use both which_ones and keep")

    return _tags_re.sub(
        functools.partial(
            _remove_tag,
            which_ones={tag.lower() for tag in which_ones} if which_ones else (),
            keep={tag.lower() for tag in keep} if keep else (),
        ),
        to_unicode(text, encoding),
    )


@functools.lru_cache(maxsize=256)
def _build_remove_tags_pattern(tags_tuple: tuple[str, ...]) -> re.Pattern[str]:
    tags = "|".join(re.escape(tag) for tag in tags_tuple)
    # The end tag closes on the tag name followed by whitespace, "/" or ">",
    # so `</script >`, `</script\n>`, `</script/>` and `</script foo>` all end
    # the element, as browsers treat them. Requiring a bare `</tag>` left the
    # content (and anything it hides, e.g. a <meta refresh>) in place. The
    # trailing run stays [^<>]* so it can't cross into the next tag and match
    # super-linearly.
    pattern = rf"""
        <(?P<tag>{tags})\b(?:{_TAG_BODY}>|[^<>]*>)
        .*?</(?P=tag)(?=[\s/>])[^<>]*>
        |
        <(?P<tag2>{tags})\b(?:{_TAG_BODY}/>|[^<>]*/>)
    """
    return re.compile(pattern, re.IGNORECASE | re.DOTALL | re.VERBOSE)


def remove_tags_with_content(
    text: str | bytes, which_ones: Iterable[str] = (), encoding: str | None = None
) -> str:
    """Remove tags and their content.

    `which_ones` is a tuple of which tags to remove including their content.
    If is empty, returns the string unmodified.

    >>> import w3lib.html
    >>> doc = '<div><p><b>This is a link:</b> <a href="http://www.example.com">example</a></p></div>'
    >>> w3lib.html.remove_tags_with_content(doc, which_ones=('b',))
    '<div><p> <a href="http://www.example.com">example</a></p></div>'
    >>>

    """

    utext = to_unicode(text, encoding)

    if not which_ones:
        return utext

    pattern = _build_remove_tags_pattern(tuple(sorted(set(which_ones))))
    return pattern.sub("", utext)


def replace_escape_chars(
    text: str | bytes,
    which_ones: Iterable[str] = ("\n", "\t", "\r"),
    replace_by: str | bytes = "",
    encoding: str | None = None,
) -> str:
    r"""Remove escape characters.

    `which_ones` is a tuple of which escape characters we want to remove.
    By default removes ``\n``, ``\t``, ``\r``.

    `replace_by` is the string to replace the escape characters by.
    It defaults to ``''``, meaning the escape characters are removed.

    """

    utext = to_unicode(text, encoding)
    for ec in which_ones:
        utext = utext.replace(ec, to_unicode(replace_by, encoding))
    return utext


def unquote_markup(
    text: str | bytes,
    keep: Iterable[str] = (),
    remove_illegal: bool = True,
    encoding: str | None = None,
) -> str:
    """
    This function receives markup as a text (always a unicode string or
    a UTF-8 encoded string) and does the following:

    1. removes entities (except the ones in `keep`) from any part of it
        that is not inside a CDATA
    2. searches for CDATAs and extracts their text (if any) without modifying it.
    3. removes the found CDATAs

    """

    utext = to_unicode(text, encoding)
    ret = []
    offset = 0

    # Scan for CDATA sections linearly.
    while True:
        start = utext.find(_CDATA_START, offset)
        if start == -1:
            break
        data_start = start + len(_CDATA_START)
        end = utext.find(_CDATA_END, data_start)
        if end == -1:
            # Unterminated CDATA
            break

        if offset < start:
            ret.append(
                replace_entities(
                    utext[offset:start],
                    keep=keep,
                    remove_illegal=remove_illegal,
                )
            )

        ret.append(utext[data_start:end])
        offset = end + len(_CDATA_END)

    if offset < len(utext):
        ret.append(
            replace_entities(
                utext[offset:],
                keep=keep,
                remove_illegal=remove_illegal,
            )
        )

    return "".join(ret)


def get_base_url(
    text: str | bytes, baseurl: str | bytes = "", encoding: str = "utf-8"
) -> str:
    """Return the base url if declared in the given HTML `text`,
    relative to the given base url.

    If no base url is found, the given `baseurl` is returned.

    """

    # Most documents declare no base url, so ruling one out in the bytes saves
    # decoding them. A hit falls through to the scan below, which decides: a
    # byte sequence that spells "<base" is not necessarily a tag, e.g. in a
    # multi-byte encoding it can be part of a character.
    if (
        isinstance(text, bytes)
        and _scannable(encoding)
        and not _base_bytes_re.search(text)
    ):
        return safe_url_string(baseurl)

    utext = to_unicode(text, encoding)
    if _base_re.search(utext):
        for m in _base_scan_re.finditer(utext):
            if url := m.group("url"):
                return urljoin(
                    safe_url_string(baseurl), safe_url_string(url, encoding=encoding)
                )
    return safe_url_string(baseurl)


def get_meta_refresh(
    text: str | bytes,
    baseurl: str = "",
    encoding: str = "utf-8",
    ignore_tags: Iterable[str] = ("script", "noscript"),
) -> tuple[None, None] | tuple[float, str]:
    """Return the http-equiv parameter of the HTML meta element from the given
    HTML text and return a tuple ``(interval, url)`` where interval is a float
    containing the delay in seconds (or zero if not present) and url is a
    string with the absolute url to redirect.

    If no meta redirect is found, ``(None, None)`` is returned.

    """
    ignored = tuple(sorted({tag.lower() for tag in ignore_tags}))

    # Most documents declare no refresh, so ruling one out in the bytes saves
    # decoding them. A hit falls through to the scan of the decoded document,
    # which decides: a byte sequence that spells a tag is not necessarily one,
    # e.g. in a multi-byte encoding it can be part of a character.
    if isinstance(text, bytes) and _scannable(encoding):
        matches = _build_meta_scan_bytes_pattern(ignored).finditer(text)
        if not any(
            (attrs := match.group("attrs")) and b"refresh" in attrs.lower()
            for match in matches
        ):
            return None, None

    utext = to_unicode(text, encoding)
    if not _meta_re.search(utext):
        return None, None

    for tag in _build_meta_scan_pattern(ignored).finditer(utext):
        attrs = tag.group("attrs")

        if attrs is None or "refresh" not in attrs.lower():
            continue

        if "&" in attrs:
            attrs = replace_entities(attrs)

        has_refresh_pragma = False
        interval: float | None = None
        url: str | None = None
        for name, value in iter_tag_attributes(attrs):
            match name:
                case "http-equiv":
                    if "refresh" in value.lower():
                        has_refresh_pragma = True
                case "content":
                    if interval is None and (
                        m := _meta_refresh_content_re.match(value)
                    ):
                        interval = float(m.group("int"))
                        url = m.group("url")

        if has_refresh_pragma and interval is not None:
            assert url is not None
            url = safe_url_string(url.strip(" \"'"), encoding)
            return interval, urljoin(baseurl, url)

    return None, None


def strip_html5_whitespace(text: str) -> str:
    r"""
    Strip all leading and trailing space characters (as defined in
    https://www.w3.org/TR/html5/infrastructure.html#space-character).

    Such stripping is useful e.g. for processing HTML element attributes which
    contain URLs, like ``href``, ``src`` or form ``action`` - HTML5 standard
    defines them as "valid URL potentially surrounded by spaces"
    or "valid non-empty URL potentially surrounded by spaces".

    >>> strip_html5_whitespace(' hello\n')
    'hello'
    """
    return text.strip(HTML5_WHITESPACE)
