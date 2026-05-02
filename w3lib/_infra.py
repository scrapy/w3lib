# https://infra.spec.whatwg.org/
import string
from typing import Final

# https://infra.spec.whatwg.org/commit-snapshots/59e0d16c1e3ba0e77c6a60bfc69a0929b8ffaa5d/#code-points
_ASCII_TAB_OR_NEWLINE: Final = "\t\n\r"
_ASCII_WHITESPACE: Final = "\t\n\x0c\r "
_C0_CONTROL: Final = "".join(chr(n) for n in range(32))
_C0_CONTROL_OR_SPACE: Final = _C0_CONTROL + " "
_ASCII_DIGIT: Final = string.digits
_ASCII_HEX_DIGIT: Final = string.hexdigits
_ASCII_ALPHA: Final = string.ascii_letters
_ASCII_ALPHANUMERIC: Final = string.ascii_letters + string.digits
