from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def to_unicode(
    text: str | bytes, encoding: str | None = None, errors: str = "strict"
) -> str:
    """Return the unicode representation of a bytes object `text`. If `text`
    is already an unicode object, return it as-is."""
    if isinstance(text, str):
        return text
    if not isinstance(text, (bytes, str)):
        raise TypeError(
            f"to_unicode must receive bytes or str, got {type(text).__name__}"
        )
    if encoding is None:
        encoding = "utf-8"
    return text.decode(encoding, errors)


_ASCII = bytes(range(128))
_ASCII_TEXT = _ASCII.decode()


@lru_cache(maxsize=64)
def _ascii_compatible(encoding: str | None) -> bool:
    """Return whether ASCII bytes decode to the same ASCII characters under
    *encoding*.

    Unknown encodings are reported as not compatible.
    """
    try:
        return _ASCII.decode(encoding or "utf-8", "replace") == _ASCII_TEXT
    except LookupError:
        return False


# Bytes that an encoding can drop when decoding, dividing a character
# sequence without leaving a trace in the text: ESC ( B redesignates ASCII
# while ASCII is already in use, and SO and SI shift between character sets.
_DROPPED = (b"\x1b(B", b"\x0e", b"\x0f")


@lru_cache(maxsize=64)
def _scannable(encoding: str | None) -> bool:
    r"""Return whether every character sequence of a document written in
    *encoding* is a byte sequence of its undecoded bytes, so that markup that
    the bytes do not contain is markup that the document does not contain.

    It takes ASCII compatibility, which makes ASCII characters their own
    bytes, and an encoding that cannot write those bytes apart, e.g.
    ``b"<ba\x1b(Bse"`` decodes to ``"<base"`` under ISO-2022-JP.
    """
    if not _ascii_compatible(encoding):
        return False
    return all(
        (b"a" + dropped + b"b").decode(encoding or "utf-8", "replace") != "ab"
        for dropped in _DROPPED
    )


# One attribute: a name and, optionally, a value, quoted or not. Each quoting
# style captures its own group, so a matched value needs no quote stripping.
_attr_re = re.compile(
    r"""(?P<name>[^\s<>/=]+)  # name
    (?:\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s"'>]*)))?""",
    re.VERBOSE,
)


def iter_tag_attributes(attrs: str) -> Iterable[tuple[str, str]]:
    """Yield ``(name, value)`` for every attribute with a value in ``attrs``,
    the text of one tag after its name, in order.

    ``name`` is lowercased, and ``value`` has its quotes removed, if any.
    """
    # finditer() matches one attribute at a time, from where the previous one
    # ended, so a crafted tag cannot make it backtrack across attributes.
    for attr in _attr_re.finditer(attrs):
        # A valueless attribute matches the name group and nothing after it.
        if attr.lastindex == 1:
            continue
        name, double, single, bare = attr.groups()
        # Exactly one value group matched; the last "" covers all three being
        # empty, which an empty value in any quoting style produces.
        yield name.lower(), double or single or bare or ""
