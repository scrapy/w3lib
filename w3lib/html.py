"""
Functions for dealing with markup text
"""

from __future__ import annotations

import functools
import re
from html.entities import name2codepoint
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from w3lib.url import safe_url_string
from w3lib.util import to_unicode

if TYPE_CHECKING:
    from collections.abc import Iterable


_ent_re = re.compile(
    r"&((?P<named>[a-z\d]+)|#(?P<dec>\d+)|#x(?P<hex>[a-f\d]+))(?P<semicolon>;?)",
    re.IGNORECASE,
)
_tag_re = re.compile(r"<[a-zA-Z\/!][^<>]*>")
_baseurl_re = re.compile(
    r"<base\s[^<>]*href\s*=\s*[\"\']\s*([^\"\'\s]+)\s*[\"\']", re.IGNORECASE
)
_meta_refresh_re = re.compile(
    r'<meta\s[^>]*http-equiv[^>]*refresh[^>]*content\s*=\s*(?P<quote>["\'])(?P<int>(\d*\.)?\d+)\s*;\s*url=\s*(?P<url>.*?)(?P=quote)',
    re.DOTALL | re.IGNORECASE,
)
_meta_refresh_re2 = re.compile(
    r'<meta\s[^>]*content\s*=\s*(?P<quote>["\'])(?P<int>(\d*\.)?\d+)\s*;\s*url=\s*(?P<url>.*?)(?P=quote)[^>]*?\shttp-equiv\s*=[^>]*refresh',
    re.DOTALL | re.IGNORECASE,
)

_cdata_re = re.compile(
    r"((?P<cdata_s><!\[CDATA\[)(?P<cdata_d>.*?)(?P<cdata_e>\]\]>))", re.DOTALL
)
_tags_re = re.compile("</?([^ <>/]+)[^<>]*>", re.IGNORECASE)
_meta_tag_re = re.compile(r"<meta\b[^<>]*>", re.IGNORECASE)


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
    tag = m.group(1).lower()

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
    pattern = rf"""
        <(?P<tag>{tags})\b[^<>]*>.*?</(?P=tag)>
        |
        <(?P<tag2>{tags})\b[^<>]*/>
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

    for match in _cdata_re.finditer(utext):
        start, end = match.span(1)

        if offset < start:
            ret.append(
                replace_entities(
                    utext[offset:start],
                    keep=keep,
                    remove_illegal=remove_illegal,
                )
            )

        ret.append(match.group("cdata_d"))
        offset = end

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

    utext = remove_comments(text, encoding=encoding)
    if m := _baseurl_re.search(utext):
        return urljoin(
            safe_url_string(baseurl), safe_url_string(m.group(1), encoding=encoding)
        )
    return safe_url_string(baseurl)


def get_meta_refresh(
    text: str | bytes,
    baseurl: str = "",
    encoding: str = "utf-8",
    ignore_tags: Iterable[str] = ("script", "noscript"),
) -> tuple[None, None] | tuple[float, str]:
    """Return the http-equiv parameter of the HTML meta element from the given
    HTML text and return a tuple ``(interval, url)`` where interval is an integer
    containing the delay in seconds (or zero if not present) and url is a
    string with the absolute url to redirect.

    If no meta redirect is found, ``(None, None)`` is returned.

    """
    utext = to_unicode(text, encoding)

    if ignore_tags:
        utext = remove_tags_with_content(utext, ignore_tags)

    utext = remove_comments(utext)

    for tag in _meta_tag_re.finditer(utext):
        raw_tag = tag.group(0)

        if "refresh" not in raw_tag.lower():
            continue

        if "&" in raw_tag:
            raw_tag = replace_entities(raw_tag)

        if m := _meta_refresh_re.search(raw_tag) or _meta_refresh_re2.search(raw_tag):
            interval = float(m.group("int"))
            url = safe_url_string(m.group("url").strip(" \"'"), encoding)
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
