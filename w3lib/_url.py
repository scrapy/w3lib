# pylint: disable=protected-access,too-many-instance-attributes,too-many-locals,too-many-nested-blocks,too-many-statements

# https://url.spec.whatwg.org/

from collections import deque
from enum import auto, Enum
from itertools import chain
from math import floor
from typing import List, Optional, Union

from ._encoding import (
    _encode_or_fail,
    _get_encoder,
    _get_output_encoding,
)
from ._infra import (
    _ASCII_ALPHA,
    _ASCII_ALPHANUMERIC,
    _ASCII_DIGIT,
    _ASCII_HEX_DIGIT,
    _ASCII_TAB_OR_NEWLINE,
    _C0_CONTROL,
    _C0_CONTROL_OR_SPACE,
    _is_noncharacter_code_point_id,
    _is_surrogate_code_point_id,
)
from ._util import _PercentEncodeSet

_ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE = {
    ord(char): None for char in _ASCII_TAB_OR_NEWLINE
}


class _State(Enum):
    SCHEME_START = auto()
    SCHEME = auto()
    NO_SCHEME = auto()
    SPECIAL_RELATIVE_OR_AUTHORITY = auto()
    PATH_OR_AUTHORITY = auto()
    RELATIVE = auto()
    RELATIVE_SLASH = auto()
    SPECIAL_AUTHORITY_SLASHES = auto()
    SPECIAL_AUTHORITY_IGNORE_SLASHES = auto()
    AUTHORITY = auto()
    HOST = auto()
    PORT = auto()
    FILE = auto()
    FILE_SLASH = auto()
    FILE_HOST = auto()
    PATH_START = auto()
    PATH = auto()
    OPAQUE_PATH = auto()
    QUERY = auto()
    FRAGMENT = auto()


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#default-port
_DEFAULT_PORTS = {
    "ftp": 21,
    "file": None,
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
}


class _URL:
    scheme: str = ""
    username: str = ""
    password: str = ""
    host: Union[None, int, List[int], str] = None
    port: Optional[int] = None
    path: Union[str, List[str]]
    query: Optional[str] = None
    fragment: Optional[str] = None

    # Indicates whether a color (:) separating a username from a password
    # existed in the parsed URL. This enables :func:`_serialize_url` to
    # generate a URL that matches the input URL, if desired.
    _password_token_seen: bool = False

    def __init__(self) -> None:
        self.path = []

    def has_opaque_path(self):
        return isinstance(self.path, str)

    def is_special(self):
        return self.scheme in _DEFAULT_PORTS


_SCHEME_CHARS = _ASCII_ALPHANUMERIC + "+-."


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#shorten-a-urls-path
def _shorten_path(url: _URL):
    path = url.path
    if url.scheme == "file" and len(path) == 1 and _is_windows_drive_letter(path[0]):
        return
    url.path = path[:-1]


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#utf-8-percent-encode
def _percent_encode_after_encoding(
    input,
    *,
    encoding: str,
    percent_encode_set: _PercentEncodeSet,
    space_as_plus: bool = False,
):
    encoder = _get_encoder(encoding)
    input_queue = deque(input)
    output = ""
    potential_error = 0

    while potential_error is not None:
        encode_output = deque()
        potential_error = _encode_or_fail(
            input=input_queue,
            encoder=encoder,
            output=encode_output,
        )
        for byte in encode_output:
            if space_as_plus and byte == b" ":
                output += "+"
                continue
            isomorph = byte.decode()
            if isomorph not in percent_encode_set:
                output += isomorph
            else:
                output += f"%{byte[0]:X}"
        if potential_error is not None:
            output += f"%26%23{ord(potential_error)}%3B"

    return output


_C0_CONTROL_PERCENT_ENCODE_SET = _PercentEncodeSet(
    _C0_CONTROL,
    greater_than="~",
)
_FRAGMENT_PERCENT_ENCODE_SET = _C0_CONTROL_PERCENT_ENCODE_SET + ' "<>`'
_QUERY_PERCENT_ENCODE_SET = _C0_CONTROL_PERCENT_ENCODE_SET + ' "#<>'
_SPECIAL_QUERY_PERCENT_ENCODE_SET = _QUERY_PERCENT_ENCODE_SET + "'"
_PATH_PERCENT_ENCODE_SET = _QUERY_PERCENT_ENCODE_SET + "?`{}"
_USERINFO_PERCENT_ENCODE_SET = _PATH_PERCENT_ENCODE_SET + "/:;=@[\\]^|"

# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#forbidden-host-code-point
_FORBIDDEN_HOST_CODE_POINTS = "\x00\t\n\r #/:<>?@[\\]^|"
_FORBIDDEN_DOMAIN_CODE_POINTS = _FORBIDDEN_HOST_CODE_POINTS + _C0_CONTROL + "%\x7F"

_EOF = object()


def _parse_ipv6(input: str):
    address = [0] * 8
    piece_index = 0
    compress = None
    pointer = 0
    input_lengh = len(input)
    if input[pointer] == ":":
        if input[pointer + 1] != ":":
            raise ValueError
        pointer += 2
        piece_index += 1
        compress = piece_index
    while pointer < input_lengh:
        if piece_index == 8:
            raise ValueError
        if input[pointer] == ":":
            if compress is not None:
                raise ValueError
            pointer += 1
            piece_index += 1
            compress = piece_index
            continue
        value = length = 0
        while length < 4 and input[pointer] in _ASCII_HEX_DIGIT:
            value = value * 0x10 + int(input[pointer], base=16)
            pointer += 1
            length += 1
        if input[pointer] == ".":
            if length == 0:
                raise ValueError
            pointer -= length
            if piece_index > 6:
                raise ValueError
            numbers_seen = 0
            while pointer < input_lengh:
                ipv4_piece = None
                if numbers_seen > 0:
                    if input[pointer] == "." and numbers_seen < 4:
                        pointer += 1
                    else:
                        raise ValueError
                if input[pointer] not in _ASCII_DIGIT:
                    raise ValueError
                while input[pointer] in _ASCII_DIGIT:
                    number = int(input[pointer])
                    if ipv4_piece is None:
                        ipv4_piece = number
                    elif ipv4_piece == 0:
                        raise ValueError
                    else:
                        ipv4_piece = ipv4_piece * 10 + number
                    if ipv4_piece > 255:
                        raise ValueError
                    pointer += 1
                address[piece_index] = address[piece_index] * 0x100 + ipv4_piece
                numbers_seen += 1
                if numbers_seen in (2, 4):
                    piece_index += 1
            if numbers_seen != 4:
                raise ValueError
            break
        if input[pointer] == ":":
            pointer += 1
            if pointer >= input_lengh:
                raise ValueError
        elif pointer < input_lengh:
            raise ValueError
        address[piece_index] = value
        piece_index += 1
    if compress is not None:
        swaps = piece_index - compress
        piece_index = 7
        while piece_index != 0 and swaps > 0:
            address[piece_index], address[compress + swaps - 1] = (
                address[compress + swaps - 1],
                address[piece_index],
            )
            piece_index -= 1
            swaps -= 1
    elif compress is None and piece_index != 8:
        raise ValueError
    return address


def _utf_8_percent_encode(
    input: str,
    percent_encode_set: _PercentEncodeSet,
):
    return _percent_encode_after_encoding(
        input,
        encoding="utf-8",
        percent_encode_set=percent_encode_set,
    )


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-opaque-host-parser
def _parse_opaque_host(input: str):
    for code_point in input:
        if code_point in _FORBIDDEN_HOST_CODE_POINTS:
            raise ValueError
    return _utf_8_percent_encode(input, _C0_CONTROL_PERCENT_ENCODE_SET)


_ASCII_HEX_BYTES = tuple(
    chain(
        range(0x30, 0x39 + 1),
        range(0x41, 0x46 + 1),
        range(0x61, 0x66 + 1),
    )
)


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#percent-decode
def _percent_decode(input: bytes):
    output = b""
    pointer = 0
    input_length = len(input)
    while pointer < input_length:
        byte = input[pointer]
        if byte != 0x25 or (
            byte == 0x25
            and (
                pointer + 2 >= input_length
                or input[pointer + 1] not in _ASCII_HEX_BYTES
                or input[pointer + 2] not in _ASCII_HEX_BYTES
            )
        ):
            output += b"%c" % byte
        else:
            byte_hex = b"%c%c" % (input[pointer + 1], input[pointer + 2])
            byte_point = int(byte_hex, base=16)
            output += b"%c" % byte_point
            pointer += 2
        pointer += 1
    return output


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#string-percent-decode
def _percent_decode_string(input: str):
    return _percent_decode(input.encode())


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#ipv4-number-parser
def _parse_ipv4_number(input: str):
    if not input:
        raise ValueError
    validation_error = False
    r = 10
    if len(input) >= 2:
        if input[:2] in ("0X", "0x"):
            validation_error = True
            input = input[2:]
            r = 16
        elif input[0] == "0":
            validation_error = True
            input = input[1:]
            r = 8
    if not input:
        return (0, True)
    return (int(input, base=r), validation_error)


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#ends-in-a-number-checker
def _ends_in_number(input: str):
    parts = input.split(".")
    if parts and parts[-1] == "":
        if len(parts) == 1:
            return False
        parts = parts[:-1]
    last = parts[-1]
    if last and all(code_point in _ASCII_DIGIT for code_point in last):
        return True
    try:
        _parse_ipv4_number(last)
    except ValueError:
        return False
    return True


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-ipv4-parser
def _parse_ipv4(input: str):
    parts = input.split(".")
    if parts and not parts[-1]:
        parts = parts[:-1]
    if len(parts) > 4:
        raise ValueError
    numbers = []
    for part in parts:
        result = _parse_ipv4_number(part)
        numbers += result[0]
    if any(item > 255 for item in numbers[:-1]):
        raise ValueError
    if numbers[-1] >= 256 ** (5 - len(numbers)):
        raise ValueError
    ipv4 = numbers[-1]
    counter = 0
    for n in numbers[:-1]:
        ipv4 += n * 256 ** (3 - counter)
        counter += 1
    return ipv4


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-host-parser
def _parse_host(input: str, *, is_special=True):
    if input.startswith("["):
        if not input.endswith("]"):
            raise ValueError
        return _parse_ipv6(input[1:-1])
    if not is_special:
        return _parse_opaque_host(input)
    domain = _percent_decode_string(input).decode()
    ascii_domain = domain.encode("idna").decode()
    for code_point in ascii_domain:
        if code_point in _FORBIDDEN_DOMAIN_CODE_POINTS:
            raise ValueError
    if _ends_in_number(ascii_domain):
        return _parse_ipv4(ascii_domain)
    return ascii_domain


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#windows-drive-letter
def _is_windows_drive_letter(input: str):
    return len(input) == 2 and input[0] in _ASCII_ALPHA and input[1] in ":|"


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#start-with-a-windows-drive-letter
def _starts_with_windows_drive_letter(input: str):
    input_length = len(input)
    return (
        input_length >= 2
        and _is_windows_drive_letter(input[:2])
        and (input_length == 2 or input[2] in "/\\?#")
    )


_ASCII_URL_CODE_POINTS = _ASCII_ALPHANUMERIC + "!$&'()*+,-./:;=?@_~"


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#url-code-points
def _is_url_code_point(code_point: str):
    if code_point in _ASCII_URL_CODE_POINTS:
        return True
    code_point_id = ord(code_point)
    if code_point_id < 0xA0:
        return False
    if code_point_id > 0x10FFFD:
        return False
    if _is_surrogate_code_point_id(code_point_id):
        return False
    if _is_noncharacter_code_point_id(code_point_id):
        return False
    return True


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#double-dot-path-segment
def _is_double_dot_path_segment(input: str):
    return input in (
        "..",
        ".%2e",
        ".%2E",
        "%2e.",
        "%2E.",
        "%2e%2e",
        "%2e%2E",
        "%2E%2e",
        "%2E%2E",
    )


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#single-dot-path-segment
def _is_single_dot_path_segment(input: str):
    return input in (
        "." "%2e",
        "%2E",
    )


def _parse_url(
    url: str,
    *,
    base_url: str = None,
    encoding: str = "utf-8",
    userinfo_percent_encode_set: _PercentEncodeSet = _USERINFO_PERCENT_ENCODE_SET,
) -> _URL:
    """Return a :class:`_URL` object built from *url*, *base_url* and
    *encoding*, following the URL parsing algorithm defined in the `URL living
    standard`_.

    .. _URL living standard: https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#url-parsing

    Additional parameters allow to deviate from the standard for specific use
    cases:

    -   *userinfo_percent_encode_set* allows customizing which characters found
        in the user authroization part of the input URL need to be
        percent-encoded.
    """

    # Additional deviations from the standard are implemented but not covered
    # in the docstring above because they do not affect public APIs of this
    # function or of the :class:`_URL`` output class:
    #
    # -   The ``passwordTokenSeen`` variable from the standard algorithm is
    #     stored into :attr:`_URL._password_token_seen`, to allow
    #     :func:`_serialize_url` to distinguish when a password was missing
    #     from the parsed URL (e.g. ``a://a@example.com``) and when it was
    #     explicitly an empty string (e.g. ``a://a:@example.com``), so that its
    #     output can match the original parsed URL if desired.

    input = url
    if base_url is not None:
        base = _parse_url(base_url, encoding=encoding)
    else:
        base = None
    encoding = _get_output_encoding(encoding)

    url = _URL()
    state = _State.SCHEME_START
    buffer = ""
    at_sign_seen = inside_brackets = False
    pointer = 0

    input = input.strip(_C0_CONTROL_OR_SPACE)
    input = input.translate(_ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE)
    input_length = len(input)

    while True:
        try:
            c = input[pointer]
        except IndexError:
            c = _EOF

        if state == _State.SCHEME_START:
            if c is not _EOF and c in _ASCII_ALPHA:
                buffer += c.lower()
                state = _State.SCHEME
            else:
                state = _State.NO_SCHEME
                pointer -= 1

        elif state == _State.SCHEME:
            if c is not _EOF and c in _SCHEME_CHARS:
                buffer += c.lower()
            elif c == ":":
                url.scheme = buffer
                buffer = ""
                if url.scheme == "file":
                    state = _State.FILE
                elif url.is_special():
                    if base is not None and base.scheme == url.scheme:
                        state = _State.SPECIAL_RELATIVE_OR_AUTHORITY
                    else:
                        state = _State.SPECIAL_AUTHORITY_SLASHES
                elif input[pointer + 1] == "/":
                    state = _State.PATH_OR_AUTHORITY
                    pointer += 1
                else:
                    url.path = ""
                    state = _State.OPAQUE_PATH
            else:
                buffer = ""
                state = _State.NO_SCHEME
                pointer = -1

        elif state == _State.NO_SCHEME:
            if base is None:
                raise ValueError
            if base.has_opaque_path():
                if c != "#":
                    raise ValueError
                url.scheme = base.scheme
                url.path = base.path
                url.query = base.query
                url.fragment = ""
                state = _State.FRAGMENT
            else:
                if base.scheme != "file":
                    state = _State.RELATIVE
                else:
                    state = _State.FILE
                pointer -= 1

        elif state == _State.SPECIAL_RELATIVE_OR_AUTHORITY:
            if c == "/" and input[pointer + 1 : 1] == "/":
                state = _State.SPECIAL_AUTHORITY_IGNORE_SLASHES
                pointer += 1
            else:
                state = _State.RELATIVE
                pointer -= 1

        elif state == _State.PATH_OR_AUTHORITY:
            if c == "/":
                state = _State.AUTHORITY
            else:
                state = _State.PATH
                pointer -= 1

        elif state == _State.RELATIVE:
            url.scheme = base.scheme
            if c == "/":
                state = _State.RELATIVE
            elif url.is_special() and c == "\\":
                state = _State.RELATIVE_SLASH
            else:
                url.username = base.username
                url.password = base.password
                url.host = base.host
                url.port = base.port
                url.path = base.path
                url.query = base.query
                if c == "?":
                    url.query = ""
                    state = _State.QUERY
                elif c == "#":
                    url.fragment = ""
                    state = _State.FRAGMENT
                elif pointer < input_length:
                    url.query = None
                    _shorten_path(url)
                    state = _State.PATH
                    pointer -= 1

        elif state == _State.RELATIVE_SLASH:
            if url.is_special() and c is not _EOF and c in "/\\":
                state = _State.SPECIAL_AUTHORITY_IGNORE_SLASHES
            elif c == "/":
                state = _State.AUTHORITY
            else:
                url.username = base.username
                url.password = base.password
                url.host = base.host
                url.port = base.port
                state = _State.PATH
                pointer -= 1

        elif state == _State.SPECIAL_AUTHORITY_SLASHES:
            if c == "/" and input[pointer + 1] == "/":
                state = _State.SPECIAL_AUTHORITY_IGNORE_SLASHES
                pointer += 1
            else:
                state = _State.SPECIAL_AUTHORITY_IGNORE_SLASHES
                pointer -= 1

        elif state == _State.SPECIAL_AUTHORITY_IGNORE_SLASHES:
            if c is not _EOF and c not in "/\\":
                state = _State.AUTHORITY
                pointer -= 1

        elif state == _State.AUTHORITY:
            if c == "@":
                if at_sign_seen:
                    buffer = "%40" + buffer
                at_sign_seen = True
                buffer_length = len(buffer)
                for i, code_point in enumerate(buffer):
                    if code_point == ":" and not url._password_token_seen:
                        url._password_token_seen = True
                        continue
                    if code_point == "%" and "%" in userinfo_percent_encode_set:
                        if (
                            i + 2 >= buffer_length
                            or buffer[i + 1] not in _ASCII_HEX_DIGIT
                            or buffer[i + 2] not in _ASCII_HEX_DIGIT
                        ):
                            encoded_code_points = "%25"
                        else:
                            encoded_code_points = "%"
                    else:
                        encoded_code_points = _utf_8_percent_encode(
                            code_point,
                            userinfo_percent_encode_set,
                        )
                    if url._password_token_seen:
                        url.password += encoded_code_points
                    else:
                        url.username += encoded_code_points
                buffer = ""
            elif c is _EOF or c in "/?#" or url.is_special() and c == "\\":
                if at_sign_seen and not buffer:
                    raise ValueError
                pointer -= len(buffer) + 1
                buffer = ""
                state = _State.HOST
            else:
                buffer += c

        elif state == _State.HOST:
            if c == ":" and not inside_brackets:
                if not buffer:
                    raise ValueError
                host = _parse_host(buffer, is_special=url.is_special())
                url.host = host
                buffer = ""
                state = _State.PORT
            elif c is _EOF or c in "/?#" or url.is_special() and c == "\\":
                pointer -= 1
                if url.is_special() and not buffer:
                    raise ValueError
                host = _parse_host(buffer, is_special=url.is_special())
                url.host = host
                buffer = ""
                state = _State.PATH_START
            else:
                if c == "[":
                    inside_brackets = True
                elif c == "]":
                    inside_brackets = False
                buffer += c

        elif state == _State.PORT:
            if c is not _EOF and c in _ASCII_DIGIT:
                buffer += c
            elif c == _EOF or c in "/?#" or url.is_special() and c == "\\":
                if buffer:
                    port = int(buffer)
                    if port > 2**16 - 1:
                        raise ValueError
                    url.port = None if _DEFAULT_PORTS.get(url.scheme) == port else port
                    buffer = ""
                state = _State.PATH_START
                pointer -= 1
            else:
                raise ValueError

        elif state == _State.FILE:
            url.scheme = "file"
            url.host = ""
            if c is not _EOF and c in "/\\":
                state = _State.FILE_SLASH
            elif base is not None and base.scheme == "file":
                url.host = base.host
                url.path = base.path
                url.query = base.query
                if c == "?":
                    url.query = ""
                    state = _State.QUERY
                elif c == "#":
                    url.fragment = ""
                    state = _State.FRAGMENT
                elif c is not _EOF:
                    url.query = None
                    if not _starts_with_windows_drive_letter(input[pointer:]):
                        _shorten_path(url)
                    else:
                        url.path = []
                    state = _State.PATH
                    pointer -= 1
            else:
                state = _State.PATH
                pointer -= 1

        elif state == _State.FILE_SLASH:
            if c is not _EOF and c in "/\\":
                state = _State.FILE_HOST
            else:
                if base is not None and base.scheme == "file":
                    url.host = base.host
                    if (
                        not _starts_with_windows_drive_letter(input[pointer:])
                        and base.path[0] in _ASCII_ALPHA
                    ):
                        url.path += base.path[0]
                state = _State.PATH
                pointer -= 1

        elif state == _State.FILE_HOST:
            if c is _EOF or c in "/\\?#":
                pointer -= 1
                if _is_windows_drive_letter(buffer):
                    state = _State.PATH
                elif not buffer:
                    url.host = ""
                    state = _State.PATH_START
                else:
                    host = _parse_host(buffer, is_special=False)
                    if host == "localhost":
                        host = ""
                    url.host = host
                    buffer = ""
                    state = _State.PATH_START
            else:
                buffer += c

        elif state == _State.PATH_START:
            if url.is_special():
                state = _State.PATH
                if c is not _EOF and c not in "/\\":
                    pointer -= 1
            elif c == "?":
                url.query = ""
                state = _State.QUERY
            elif c == "#":
                url.fragment = ""
                state = _State.FRAGMENT
            elif c is not _EOF:
                state = _State.PATH
                if c != "/":
                    pointer -= 1

        elif state == _State.PATH:
            if c is _EOF or c == "/" or (url.is_special() and c == "\\") or c in "?#":
                if _is_double_dot_path_segment(buffer):
                    _shorten_path(url)
                    if c != "/" and not (url.is_special() and c == "\\"):
                        url.path.append("")
                elif _is_single_dot_path_segment(buffer):
                    if c != "/" and not (url.is_special() and c == "\\"):
                        url.path.append("")
                else:
                    if (
                        url.scheme == "file"
                        and not url.path
                        and _is_windows_drive_letter(buffer)
                    ):
                        buffer = buffer[0] + ":" + buffer[2:]
                    url.path.append(buffer)
                buffer = ""
                if c == "?":
                    url.query = ""
                    state = _State.QUERY
                elif c == "#":
                    url.fragment = ""
                    state = _State.FRAGMENT
            else:
                buffer += _utf_8_percent_encode(c, _PATH_PERCENT_ENCODE_SET)

        elif state == _State.OPAQUE_PATH:
            if c == "?":
                url.query = ""
                state = _State.QUERY
            elif c == "#":
                url.fragment = ""
                state = _State.FRAGMENT
            elif c is not _EOF:
                encoded = _utf_8_percent_encode(
                    c,
                    _C0_CONTROL_PERCENT_ENCODE_SET,
                )
                url.path += encoded

        elif state == _State.QUERY:
            if encoding != "utf-8" and (
                not url.is_special() or url.scheme in ("ws", "wss")
            ):
                encoding = "utf-8"
            if c == "#" or c is _EOF:
                query_percent_encode_set = (
                    _SPECIAL_QUERY_PERCENT_ENCODE_SET
                    if url.is_special()
                    else _QUERY_PERCENT_ENCODE_SET
                )
                url.query += _percent_encode_after_encoding(
                    buffer,
                    encoding=encoding,
                    percent_encode_set=query_percent_encode_set,
                )
                buffer = ""
                if c == "#":
                    url.fragment = ""
                    state = _State.FRAGMENT
            elif c is not _EOF:
                buffer += c

        elif state == _State.FRAGMENT:
            if c is not _EOF:
                url.fragment += _utf_8_percent_encode(
                    c,
                    _FRAGMENT_PERCENT_ENCODE_SET,
                )

        if pointer >= input_length:
            break
        pointer += 1

    return url


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-ipv4
def _serialize_ipv4(address: int) -> str:
    output = ""
    n = address
    for i in range(1, 5):
        output = str(n % 256) + output
        if i != 4:
            output = "." + output
        n = floor(n / 256)
    return output


def _get_ipv6_first_longest_0_piece_index(address: List[int], *, min_length=2):
    index = None
    index_length = 0
    current_length = 0
    for current_index, piece in enumerate(address):
        if piece != 0:
            current_length = 0
            continue
        current_length += 1
        if current_length > index_length and current_length >= min_length:
            index = current_index + 1 - current_length
            index_length = current_length
    return index


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-ipv6-serializer
def _serialize_ipv6(address: List[int]) -> str:
    output = ""
    compress = _get_ipv6_first_longest_0_piece_index(address)
    ignore0 = False
    for piece_index in range(8):
        if ignore0:
            if not address[piece_index]:
                continue
            ignore0 = False
        if compress == piece_index:
            separator = "::" if piece_index == 0 else ":"
            output += separator
            ignore0 = True
            continue
        output += f"{address[piece_index]:x}"
        if piece_index != 7:
            output += ":"
    return output


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-host-serializer
def _serialize_host(host: Union[str, int, List[int]]):
    if isinstance(host, int):
        return _serialize_ipv4(host)
    if isinstance(host, list):
        return f"[{_serialize_ipv6(host)}]"
    return host


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#url-path-serializer
def _serialize_url_path(url: _URL) -> str:
    if url.has_opaque_path():
        return url.path
    output = ""
    for segment in url.path:
        output += f"/{segment}"
    return output


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#url-serializing
def _serialize_url(
    url: _URL,
    *,
    exclude_fragment: bool = False,
    canonicalize: Optional[bool] = None,
) -> str:
    """Return a string representation of *url* following the URL serialization
    algorithm defined in the `URL living standard`_.

    .. _URL living standard: https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-url-serializer

    If *exclude_fragment* is ``True``, the returned URL does not include
    :attr:`_URL.fragment`.

    Additional parameters allow to deviate from the standard for specific use
    cases:

    -   *canonicalize*:

        -   ``None``: Do not deviate from the standard algorithm to apply or
            prevent URL canonicalization.

        -   ``True``: Deviate from the standard as needed to make sure that
            functionally-equivalent URLs are always rendered the same way.

            This value has no effect at the moment, i.e. it applies the same
            level of canonicalization as the standard algorithm.

        -   ``False``: Deviate from the standard as needed to make sure that
            the returned URL string is as close as possible to the original URL
            string that was parsed into *url*, as long as the returned URL
            string is still a valid URL.

            At the moment, this ensures that the password separator (:) is
            included into the returned URL string as long as it was present on
            the original URL string, even if :attr:`_URL.password` is an empty
            string.
    """
    output = url.scheme + ":"
    if url.host is not None:
        output += "//"
        if url.username or url.password:
            output += url.username
            if url.password:
                output += f":{url.password}"
            elif url._password_token_seen:
                output += ":"
            output += "@"
        output += _serialize_host(url.host)
        if url.port is not None:
            output += f":{url.port}"
    elif not url.has_opaque_path() and len(url.path) > 1 and not url.path[0]:
        output += "/."
    output += _serialize_url_path(url)
    if url.query is not None:
        output += f"?{url.query}"
    if not exclude_fragment and url.fragment is not None:
        output += f"#{url.fragment}"
    return output
