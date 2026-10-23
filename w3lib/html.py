"""
Functions for dealing with markup text
"""

from __future__ import annotations

import functools
import re
import warnings
from html.entities import html5
from typing import TYPE_CHECKING

from frostwork import navigation

from w3lib._url import _SCHEME_RE
from w3lib._util import _COMMENT, _attr_re, _scannable, iter_tag_attributes, to_unicode
from w3lib.url import _urljoin, safe_url_string

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
# quote would swallow the markup in between. A tag with no "=" before its
# first ">" has no quoted value that could hold one, so both readings agree on
# it, and the plain one comes first because it is the cheaper of the two and
# the case of most tags.
_tag_re = re.compile(
    rf"""<[a-zA-Z/!][^<>=]*>|</?{_TAG_NAME}{_TAG_BODY}>|<[a-zA-Z/!][^<>]*>""",
    re.ASCII,
)
# Tag syntax is ASCII, and re.ASCII holds the scan patterns of this module to
# it: "\s" matches the whitespace that separates markup and not, say, U+3000,
# and case-insensitive matching pairs no "s" with "\u017f" nor "k" with
# "\u212a". It is also what makes a pattern and its byte counterpart match the
# same markup.


def _ignored_tags_source(ignore_tags: tuple[str, ...]) -> str:
    tags = "|".join(re.escape(tag) for tag in ignore_tags)
    # Only HTML whitespace, "/" or ">" after the name can close the element.
    # Unlike _TAG_BODY, the end-tag body consumes "<" as attribute text. Quoted
    # values also consume ">", and an unfinished value runs to the end of input.
    space = r"[\t\n\f\r ]"
    attribute = (
        rf"[^\t\n\f\r />][^\t\n\f\r />=]*+{space}*+"
        rf"(?:={space}*+(?:\"[^\"]*(?:\"|$)|'[^']*(?:'|$)|[^\t\n\f\r >]*+))?+"
    )
    # Possessive repeats keep attribute names and unquoted values from being
    # split or read again as the scanner advances through a long end tag.
    end_body = rf"(?:{space}|/|{attribute})*+(?:>|$)"
    return (
        rf"<(?P<t>{tags})\b{_TAG_BODY}>[^<]*"
        r"(?:<(?!/(?P=t)[\t\n\f\r />])[^<]*)*"
        rf"(?:</(?P=t){end_body}|$)"
    )


_base_re = re.compile("<base", re.IGNORECASE | re.ASCII)
_base_bytes_re = re.compile(rb"<base", re.IGNORECASE)
# Scan for <base> tags, consuming comments and <script>/<noscript> content
# (where a browser never parses tags) along the way. Ignorable regions come
# first in the alternation, so a <base> inside one is consumed before it can
# match; unterminated regions swallow the rest of the document, as a browser
# does. Their content is consumed in runs of characters that cannot start the
# closing delimiter, so that the large inline scripts of real pages cost a
# tight loop per run rather than a match attempt per character. The end tag
# closes on the tag name followed by HTML whitespace, "/" or ">".
#
# The text of a <base> tag after its name is captured whole and its attributes
# are then read one by one, as for <meta>.
_base_scan_re = re.compile(
    rf"""
      {_COMMENT}
    | {_ignored_tags_source(("script", "noscript"))}
    | <base\s(?P<attrs>{_TAG_BODY})
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE | re.ASCII,
)


# The refresh payload: ``3; url=...``. The url= part is required.
# The interval is ASCII digits only, and the separator after it is ";", ","
# or ASCII whitespace, as in the HTML refresh steps. The two separator
# alternatives keep their whitespace runs from overlapping, so that matching
# stays linear.
_meta_refresh_content_re = re.compile(
    r"\s*(?P<int>([0-9]*\.)?[0-9]+)(?:\s*[;,]\s*|\s+)url=\s*(?P<url>.*)",
    re.DOTALL | re.IGNORECASE | re.ASCII,
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
    (?P<name>[^ <>/]++)
                    # tag name (captured): a run of non-space, non-bracket chars,
                    # possessive so that it can't give characters back to the
                    # run below and backtrack quadratically on an unterminated
                    # tag (a "<" with a long run and no ">")
    [^<>]*          # the rest of the tag: attributes, whitespace, etc.
    >               # closing angle bracket
    """,
    re.IGNORECASE | re.VERBOSE | re.ASCII,
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
    # name followed by HTML whitespace, "/" or ">".
    #
    # The <meta> body is matched without the closing angle bracket, which is
    # not required: a tag left unterminated by the next "<" or by the end of
    # the text is still parsed, as browsers do.
    alternatives = [_COMMENT]
    if ignore_tags:
        alternatives.append(_ignored_tags_source(ignore_tags))
    alternatives.append(rf"<meta\s(?P<attrs>{_TAG_BODY})")
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

    keep = frozenset(keep)

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
            # The named character reference table is looked up as written: it
            # is case-sensitive, and only its legacy entries resolve without
            # the semicolon.
            # https://html.spec.whatwg.org/commit-snapshots/3e7b72c44ce144cee7db859cd0647af6646b6793/#named-character-reference-state
            replacement = html5.get(entity_name + groups["semicolon"])
            if replacement is not None:
                return replacement
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


_REMOVECOMMENTS_RE = re.compile(_COMMENT)


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
    tags = {tag.lower() for tag in which_ones} if which_ones else ()
    kept = {tag.lower() for tag in keep} if keep else ()

    if tags and kept:
        raise ValueError("Cannot use both which_ones and keep")

    return _tags_re.sub(
        functools.partial(_remove_tag, which_ones=tags, keep=kept),
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
        <(?P<tag>{tags})(?=[\s/>])(?:{_TAG_BODY}>|[^<>]*>)
        .*?</(?P=tag)(?=[\s/>])[^<>]*>
        |
        <(?P<tag2>{tags})(?=[\s/>])(?:{_TAG_BODY}/>|[^<>]*/>)
    """
    return re.compile(pattern, re.IGNORECASE | re.DOTALL | re.VERBOSE | re.ASCII)


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

    keep = frozenset(keep)

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


def _warn_relative_baseurl(function: str) -> None:
    warnings.warn(
        f"Passing a relative or empty baseurl to w3lib.html.{function}() is "
        "deprecated, pass the absolute URL of the document instead. In a "
        "future version, baseurl will be required, and a relative one will "
        "raise ValueError.",
        DeprecationWarning,
        stacklevel=3,
    )


def get_base_url(
    text: str | bytes,
    baseurl: str | bytes = "",
    encoding: str = "utf-8",
    *,
    max_scan: int | None = None,
) -> str:
    """Return the base URL of the HTML *text*, as a web browser finds it.

    *baseurl* is the absolute URL of the document, which is also the result
    when *text* declares no usable base URL.
    """
    if max_scan is not None:
        warnings.warn(
            "The max_scan parameter of w3lib.html.get_base_url() is deprecated "
            "and ignored.",
            DeprecationWarning,
            stacklevel=2,
        )
    url = to_unicode(baseurl, errors="percentencode")
    if _SCHEME_RE.match(url):
        nav = navigation(
            text,
            url,
            encoding if isinstance(text, bytes) else None,
            meta_refresh=False,
        )
        assert nav.base_url is not None
        return nav.base_url
    _warn_relative_baseurl("get_base_url")
    document_url = safe_url_string(baseurl)

    # Most documents declare no base url, so ruling one out in the bytes saves
    # decoding them. A hit falls through to the scan below, which decides: a
    # byte sequence that spells "<base" is not necessarily a tag, e.g. in a
    # multi-byte encoding it can be part of a character.
    if (
        isinstance(text, bytes)
        and _scannable(encoding)
        and not _base_bytes_re.search(text)
    ):
        return document_url

    utext = to_unicode(text, encoding)
    if _base_re.search(utext):
        for m in _base_scan_re.finditer(utext):
            if (attrs := m.group("attrs")) is None:
                continue
            # iter_tag_attributes drops valueless attributes, but a valueless
            # href counts as one, so read the attributes here to see it.
            for attr in _attr_re.finditer(attrs):
                if attr["name"].lower() != "href":
                    continue
                # The first <base> with an href attribute sets the base URL,
                # and the first href of that tag is the one read; an empty or
                # valueless one leaves the fallback in place, so a later <base>
                # is not read either way.
                # https://html.spec.whatwg.org/commit-snapshots/3e7b72c44ce144cee7db859cd0647af6646b6793/#set-the-frozen-base-url
                value = attr["double"] or attr["single"] or attr["bare"] or ""
                if url := value.strip(HTML5_WHITESPACE):
                    # A URL that cannot be parsed also leaves the fallback in
                    # place, e.g. a relative URL against an opaque path such as
                    # "data:…", or a host with a forbidden code point.
                    try:
                        return safe_url_string(
                            _urljoin(document_url, url), encoding=encoding
                        )
                    except ValueError:
                        pass
                return document_url
    return document_url


def _refresh(attrs: str, baseurl: str, encoding: str) -> tuple[float, str] | None:
    """Return the interval and absolute url of the refresh that *attrs*, the
    text of a <meta> tag after its name, declares, if it declares one."""
    has_refresh_pragma = False
    interval: float | None = None
    url: str | None = None
    for name, raw_value in iter_tag_attributes(attrs):
        # a reference is decoded into the value of its own attribute, so a
        # decoded quote or "=" is data, and a name is not decoded at all
        # https://html.spec.whatwg.org/commit-snapshots/3e7b72c44ce144cee7db859cd0647af6646b6793/#flush-code-points-consumed-as-a-character-reference
        value = replace_entities(raw_value) if "&" in raw_value else raw_value
        match name:
            case "http-equiv":
                if "refresh" in value.lower():
                    has_refresh_pragma = True
            case "content":
                if interval is None and (m := _meta_refresh_content_re.match(value)):
                    interval = float(m.group("int"))
                    url = m.group("url")

    if not has_refresh_pragma or interval is None:
        return None
    assert url is not None
    # A URL that cannot be parsed declares no refresh, so a later <meta> can.
    # https://html.spec.whatwg.org/commit-snapshots/3e7b72c44ce144cee7db859cd0647af6646b6793/#shared-declarative-refresh-steps
    try:
        return interval, safe_url_string(_urljoin(baseurl, url.strip(" \"'")), encoding)
    except ValueError:
        return None


_BROWSER_IGNORED_TAGS = frozenset(("script", "noscript", "template"))


def get_meta_refresh(
    text: str | bytes,
    baseurl: str = "",
    encoding: str = "utf-8",
    ignore_tags: Iterable[str] = ("script", "noscript"),
    *,
    max_scan: int | None = None,
) -> tuple[None, None] | tuple[float, str]:
    """Return ``(interval, url)`` for the meta refresh of the HTML *text*
    that a web browser follows, or ``(None, None)`` if there is none.

    *interval* is the delay in seconds, and *url* is the absolute URL to load,
    resolved against *baseurl*, the absolute URL of the document, and against
    a ``<base>`` element of *text*.

    ``<noscript>`` content counts only if *ignore_tags* does not contain
    ``"noscript"``, as in a browser with JavaScript disabled.
    """
    if max_scan is not None:
        warnings.warn(
            "The max_scan parameter of w3lib.html.get_meta_refresh() is "
            "deprecated and ignored.",
            DeprecationWarning,
            stacklevel=2,
        )
    ignored = tuple(sorted({tag.lower() for tag in ignore_tags}))
    browser_tags = _BROWSER_IGNORED_TAGS.issuperset(ignored)
    if not browser_tags:
        warnings.warn(
            "Passing ignore_tags with tags other than 'script', 'noscript' and "
            "'template' to w3lib.html.get_meta_refresh() is deprecated, and "
            "will raise ValueError in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
    absolute = _SCHEME_RE.match(baseurl)
    if not absolute:
        _warn_relative_baseurl("get_meta_refresh")
    if browser_tags and absolute:
        nav = navigation(
            text,
            baseurl,
            encoding if isinstance(text, bytes) else None,
            base_url=False,
            scripting="noscript" in ignored,
        )
        if nav.meta_refresh is None:
            return None, None
        return nav.meta_refresh.delay, nav.meta_refresh.url

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
        if refresh := _refresh(attrs, baseurl, encoding):
            return refresh

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
