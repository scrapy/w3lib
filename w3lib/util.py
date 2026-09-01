import warnings

from ._util import to_bytes, to_unicode

__all__ = ["to_bytes", "to_unicode"]

warnings.warn(
    "The w3lib.util module is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)
