from __future__ import annotations

import re
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


# One attribute: a name and, optionally, a quoted or unquoted value.
_attr_re = re.compile(
    r"""(?P<name>[^\s<>/=]+)  # name
    (?:\s*=\s*(?P<value>"[^"]*"|'[^']*'|[^\s"'>]*))?""",  # optional value
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
        value = attr.group("value")
        if value is None:
            continue
        if value[:1] in ('"', "'"):
            value = value[1:-1]
        yield attr.group("name").lower(), value
