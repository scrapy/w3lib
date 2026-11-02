import warnings

from ._util import to_bytes as to_bytes, to_unicode as to_unicode

warnings.warn(
    "The w3lib.util module is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)
