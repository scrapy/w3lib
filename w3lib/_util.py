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


_attr_re = re.compile(
    r"""\s*(?:
        (?P<name>[^\s<>/=]+)                              # attribute name
        (?:\s*=\s*(?P<value>"[^"]*"|'[^']*'|[^\s"'>]*))?  # optional value
      | [<>/=]                                            # stray character
      | \Z                                                # end of input
    )""",
    re.VERBOSE,
)


def iter_tag_attributes(attrs: str) -> Iterable[tuple[str, str | None]]:
    """Yield ``(name, value)`` for every attribute in ``attrs``, the text of
    one tag after its name.

    ``name`` is lowercased. ``value`` is ``None`` for a valueless attribute and
    the value without its quotes otherwise.
    """
    pos = 0
    while pos < len(attrs):
        # A single attribute of an already-isolated tag (no "<"/">" inside), anchored
        # with .match() at the current scan position. It always matches and always
        # advances, so scanning the whole tag stays linear even on crafted input.
        attr = _attr_re.match(attrs, pos)
        assert attr is not None
        pos = attr.end()
        name = attr.group("name")
        if name is None:
            continue
        value = attr.group("value")
        if value is not None and value[:1] in ('"', "'"):
            value = value[1:-1]
        yield name.lower(), value
