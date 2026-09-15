import warnings

from ._util import to_unicode as to_unicode

warnings.warn(
    "The w3lib.util module is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)


def to_bytes(
    text: str | bytes, encoding: str | None = None, errors: str = "strict"
) -> bytes:
    """Return the binary representation of `text`. If `text`
    is already a bytes object, return it as-is."""
    if isinstance(text, bytes):
        return text
    if not isinstance(text, str):
        raise TypeError(
            f"to_bytes must receive str or bytes, got {type(text).__name__}"
        )
    if encoding is None:
        encoding = "utf-8"
    return text.encode(encoding, errors)
