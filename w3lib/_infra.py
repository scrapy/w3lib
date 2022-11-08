# https://infra.spec.whatwg.org/

import string

# https://infra.spec.whatwg.org/commit-snapshots/59e0d16c1e3ba0e77c6a60bfc69a0929b8ffaa5d/#code-points
_ASCII_TAB_OR_NEWLINE = "\t\n\r"
_ASCII_WHITESPACE = "\t\n\x0c\r "
_C0_CONTROL = "".join(chr(n) for n in range(32))
_C0_CONTROL_OR_SPACE = _C0_CONTROL + " "
_ASCII_DIGIT = string.digits
_ASCII_HEX_DIGIT = string.hexdigits
_ASCII_ALPHA = string.ascii_letters
_ASCII_ALPHANUMERIC = string.ascii_letters + string.digits


# https://infra.spec.whatwg.org/commit-snapshots/59e0d16c1e3ba0e77c6a60bfc69a0929b8ffaa5d/#surrogate
def _is_surrogate_code_point_id(code_point_id) -> bool:
    return 0xD800 <= code_point_id <= 0xDFFF


# https://infra.spec.whatwg.org/commit-snapshots/59e0d16c1e3ba0e77c6a60bfc69a0929b8ffaa5d/#noncharacter
def _is_noncharacter_code_point_id(code_point_id) -> bool:
    if 0xFDD0 <= code_point_id <= 0xFDEF:
        return True
    return code_point_id in (
        0xFFFE,
        0xFFFF,
        0x1FFFE,
        0x1FFFF,
        0x2FFFE,
        0x2FFFF,
        0x3FFFE,
        0x3FFFF,
        0x4FFFE,
        0x4FFFF,
        0x5FFFE,
        0x5FFFF,
        0x6FFFE,
        0x6FFFF,
        0x7FFFE,
        0x7FFFF,
        0x8FFFE,
        0x8FFFF,
        0x9FFFE,
        0x9FFFF,
        0xAFFFE,
        0xAFFFF,
        0xBFFFE,
        0xBFFFF,
        0xCFFFE,
        0xCFFFF,
        0xDFFFE,
        0xDFFFF,
        0xEFFFE,
        0xEFFFF,
        0xFFFFE,
        0xFFFFF,
        0x10FFFE,
        0x10FFFF,
    )
