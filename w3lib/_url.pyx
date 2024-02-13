# pylint: disable=protected-access,too-many-instance-attributes,too-many-locals,too-many-nested-blocks,too-many-statements

import codecs
import string
from functools import lru_cache
from math import floor
from typing import AnyStr, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import unquote

from cython import bint, cfunc, declare, uchar

from . import _utr46
from ._infra import (
    _ASCII_ALPHA,
    _ASCII_ALPHANUMERIC,
    _ASCII_DIGIT,
    _ASCII_HEX_DIGIT,
    _ASCII_TAB_OR_NEWLINE,
    _ASCII_WHITESPACE,
    _C0_CONTROL,
    _C0_CONTROL_OR_SPACE,
)
from ._rfc2396 import (
    _RFC2396_ABS_PATH_PERCENT_ENCODE_SET,
    _RFC2396_FRAGMENT_PERCENT_ENCODE_SET,
    _RFC2396_QUERY_PERCENT_ENCODE_SET,
    _RFC2396_USERINFO_PERCENT_ENCODE_SET,
)
from ._rfc3986 import (
    _RFC3986_FRAGMENT_PERCENT_ENCODE_SET,
    _RFC3986_PATH_PERCENT_ENCODE_SET,
    _RFC3986_QUERY_PERCENT_ENCODE_SET,
    _RFC3986_USERINFO_PERCENT_ENCODE_SET,
)
from ._util import _PercentEncodeSet

# https://encoding.spec.whatwg.org/

CodecFunction = Callable[[AnyStr], Tuple[AnyStr, int]]
DecodeFunction = Callable[[bytes], Tuple[str, int]]
EncodeFunction = Callable[[str, str], Tuple[bytes, int]]


def _short_windows_125(last_digit: int) -> Dict[str, str]:
    return {
        label: f"windows-125{last_digit}"
        for label in (
            f"cp125{last_digit}",
            f"windows-125{last_digit}",
            f"x-cp125{last_digit}",
        )
    }


_REPLACEMENT_ENCODING = "replacement"
_UTF_8_ENCODING = "utf-8"
_UTF_16BE_ENCODING = "utf-16be"
_UTF_16LE_ENCODING = "utf-16le"

# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#concept-encoding-get
#
# Maps the labels defined in the standard to an encoding label that Python
# understands.
_LABEL_ENCODINGS = {
    **{
        label: _UTF_8_ENCODING
        for label in (
            "unicode-1-1-utf-8",
            "unicode11utf8",
            "unicode20utf8",
            "utf-8",
            "utf8",
            "x-unicode20utf8",
        )
    },
    **{
        label: "ibm866"
        for label in (
            "866",
            "cp866",
            "csibm866",
            "ibm866",
        )
    },
    **{
        label: "iso-8859-2"
        for label in (
            "csisolatin2",
            "iso-8859-2",
            "iso-ir-101",
            "iso8859-2",
            "iso88592",
            "iso_8859-2",
            "iso_8859-2:1987",
            "l2",
            "latin2",
        )
    },
    **{
        label: "iso-8859-3"
        for label in (
            "csisolatin3",
            "iso-8859-3",
            "iso-ir-109",
            "iso8859-3",
            "iso88593",
            "iso_8859-3",
            "iso_8859-3:1988",
            "l3",
            "latin3",
        )
    },
    **{
        label: "iso-8859-4"
        for label in (
            "csisolatin4",
            "iso-8859-4",
            "iso-ir-110",
            "iso8859-4",
            "iso88594",
            "iso_8859-4",
            "iso_8859-4:1988",
            "l4",
            "latin4",
        )
    },
    **{
        label: "iso-8859-5"
        for label in (
            "csisolatincyrillic",
            "cyrillic",
            "iso-8859-5",
            "iso-ir-144",
            "iso8859-5",
            "iso88595",
            "iso_8859-5",
            "iso_8859-5:1988",
        )
    },
    **{
        label: "iso-8859-6"
        for label in (
            "arabic",
            "asmo-708",
            "csiso88596e",
            "csiso88596i",
            "csisolatinarabic",
            "ecma-114",
            "iso-8859-6",
            "iso-8859-6-e",
            "iso-8859-6-i",
            "iso-ir-127",
            "iso8859-6",
            "iso88596",
            "iso_8859-6",
            "iso_8859-6:1987",
        )
    },
    **{
        label: "iso-8859-7"
        for label in (
            "csisolatingreek",
            "ecma-118",
            "elot_928",
            "greek",
            "greek8",
            "iso-8859-7",
            "iso-ir-126",
            "iso8859-7",
            "iso88597",
            "iso_8859-7",
            "iso_8859-7:1987",
            "sun_eu_greek",
        )
    },
    **{
        label: "iso-8859-8"
        for label in (
            "csiso88598e",
            "csisolatinhebrew",
            "hebrew",
            "iso-8859-8",
            "iso-8859-8-e",
            "iso-ir-138",
            "iso8859-8",
            "iso88598",
            "iso_8859-8",
            "iso_8859-8:1988",
            "visual",
        )
    },
    **{
        label: "iso-8859-8-i"
        for label in (
            "csiso88598i",
            "iso-8859-8-i",
            "logical",
        )
    },
    **{
        label: "iso-8859-10"
        for label in (
            "csisolatin6",
            "iso-8859-10",
            "iso-ir-157",
            "iso8859-10",
            "iso885910",
            "l6",
            "latin6",
        )
    },
    **{
        label: "iso-8859-10"
        for label in (
            "csisolatin6",
            "iso-8859-10",
            "iso-ir-157",
            "iso8859-10",
            "iso885910",
            "l6",
            "latin6",
        )
    },
    **{
        label: "iso-8859-13"
        for label in (
            "iso-8859-13",
            "iso8859-13",
            "iso885913",
        )
    },
    **{
        label: "iso-8859-14"
        for label in (
            "iso-8859-14",
            "iso8859-14",
            "iso885914",
        )
    },
    **{
        label: "iso-8859-15"
        for label in (
            "csisolatin9",
            "iso-8859-15",
            "iso8859-15",
            "iso885915",
            "iso_8859-15",
            "l9",
        )
    },
    "iso-8859-16": "iso-8859-16",
    **{
        label: "koi8-r"
        for label in (
            "cskoi8r",
            "koi",
            "koi8",
            "koi8-r",
            "koi8_r",
        )
    },
    **{
        label: "koi8-u"
        for label in (
            "koi8-ru",
            "koi8-u",
        )
    },
    **{
        label: "macintosh"
        for label in (
            "csmacintosh",
            "mac",
            "macintosh",
            "x-mac-roman",
        )
    },
    **{
        label: "cp874"
        for label in (
            "dos-874",
            "iso-8859-11",
            "iso8859-11",
            "iso885911",
            "tis-620",
            "windows-874",
        )
    },
    **_short_windows_125(0),
    **_short_windows_125(1),
    **{
        label: "windows-1252"
        for label in (
            "ansi_x3.4-1968",
            "ascii",
            "cp1252",
            "cp819",
            "csisolatin1",
            "ibm819",
            "iso-8859-1",
            "iso-ir-100",
            "iso8859-1",
            "iso88591",
            "iso_8859-1",
            "iso_8859-1:1987",
            "l1",
            "latin1",
            "us-ascii",
            "windows-1252",
            "x-cp1252",
        )
    },
    **_short_windows_125(3),
    **{
        label: "windows-1254"
        for label in (
            "cp1254",
            "csisolatin5",
            "iso-8859-9",
            "iso-ir-148",
            "iso8859-9",
            "iso88599",
            "iso_8859-9",
            "iso_8859-9:1989",
            "l5",
            "latin5",
            "windows-1254",
            "x-cp1254",
        )
    },
    **_short_windows_125(5),
    **_short_windows_125(6),
    **_short_windows_125(7),
    **_short_windows_125(8),
    **{
        label: "mac-cyrillic"
        for label in (
            "x-mac-cyrillic",
            "x-mac-ukrainian",
        )
    },
    **{
        label: "gbk"
        for label in (
            "chinese",
            "csgb2312",
            "csiso58gb231280",
            "gb2312",
            "gb_2312",
            "gb_2312-80",
            "gbk",
            "iso-ir-58",
            "x-gbk",
        )
    },
    "gb18030": "gb18030",
    **{
        label: "big5"
        for label in (
            "big5",
            "big5-hkscs",
            "cn-big5",
            "csbig5",
            "x-x-big5",
        )
    },
    **{
        label: "euc-jp"
        for label in (
            "cseucpkdfmtjapanese",
            "euc-jp",
            "x-euc-jp",
        )
    },
    **{
        label: "iso-2022-jp"
        for label in (
            "csiso2022jp",
            "iso-2022-jp",
        )
    },
    **{
        label: "shift_jis"
        for label in (
            "csshiftjis",
            "ms932",
            "ms_kanji",
            "shift-jis",
            "shift_jis",
            "sjis",
            "windows-31j",
            "x-sjis",
        )
    },
    **{
        label: "euc-kr"
        for label in (
            "cseuckr",
            "csksc56011987",
            "euc-kr",
            "iso-ir-149",
            "korean",
            "ks_c_5601-1987",
            "ks_c_5601-1989",
            "ksc5601",
            "ksc_5601",
            "windows-949",
        )
    },
    **{
        label: _REPLACEMENT_ENCODING
        for label in (
            "csiso2022kr",
            "hz-gb-2312",
            "iso-2022-cn",
            "iso-2022-cn-ext",
            "iso-2022-kr",
            "replacement",
        )
    },
    **{
        label: _UTF_16BE_ENCODING
        for label in (
            "unicodefffe",
            "utf-16be",
        )
    },
    **{
        label: _UTF_16LE_ENCODING
        for label in (
            "csunicode",
            "iso-10646-ucs-2",
            "ucs-2",
            "unicode",
            "unicodefeff",
            "utf-16",
            "utf-16le",
        )
    },
    "x-user-defined": "x-user-defined",
}


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#get-an-encoder
@lru_cache(maxsize=None)
def _get_encoder(encoding: str) -> EncodeFunction:
    codec_info = codecs.lookup(encoding)
    return codec_info.encode


_UTF_8_ENCODER = _get_encoder("utf-8")


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#concept-encoding-get
@lru_cache(maxsize=None)
def _get_encoding(label: str) -> str:
    label = label.strip(_ASCII_WHITESPACE).lower()
    try:
        encoding = _LABEL_ENCODINGS[label]
    except KeyError:
        raise ValueError(
            f"{label!r} does not match any encoding label from the Encoding "
            f"Standard (https://encoding.spec.whatwg.org/commit-snapshots/3721"
            f"bec25c59f5506744dfeb8e3af7783e2f0f52/#ref-for-name%E2%91%A1)"
        )
    return encoding


_OUTPUT_ENCODING_UTF8_ENCODINGS = (
    _REPLACEMENT_ENCODING,
    _UTF_16BE_ENCODING,
    _UTF_16LE_ENCODING,
)


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#output-encodings
@cfunc
def _get_output_encoding(encoding: str) -> str:
    encoding = _get_encoding(encoding)
    if encoding in _OUTPUT_ENCODING_UTF8_ENCODINGS:
        return _UTF_8_ENCODING
    return encoding


# https://url.spec.whatwg.org/

_ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE = {
    ord(char): None for char in _ASCII_TAB_OR_NEWLINE
}

SCHEME_START = declare(uchar, 0)
SCHEME = declare(uchar, 1)
NO_SCHEME = declare(uchar, 2)
SPECIAL_RELATIVE_OR_AUTHORITY = declare(uchar, 3)
PATH_OR_AUTHORITY = declare(uchar, 4)
RELATIVE = declare(uchar, 5)
RELATIVE_SLASH = declare(uchar, 6)
SPECIAL_AUTHORITY_SLASHES = declare(uchar, 7)
SPECIAL_AUTHORITY_IGNORE_SLASHES = declare(uchar, 8)
AUTHORITY = declare(uchar, 9)
HOST = declare(uchar, 10)
PORT = declare(uchar, 11)
FILE = declare(uchar, 12)
FILE_SLASH = declare(uchar, 13)
FILE_HOST = declare(uchar, 14)
PATH_START = declare(uchar, 15)
PATH = declare(uchar, 16)
OPAQUE_PATH = declare(uchar, 17)
QUERY = declare(uchar, 18)
FRAGMENT = declare(uchar, 19)


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#default-port
_DEFAULT_PORTS = {
    "ftp": 21,
    "file": None,
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
}
_SPECIAL_SCHEMES = set(_DEFAULT_PORTS.keys())


class _URL:
    _scheme: str = ""
    username: str = ""
    password: str = ""
    hostname: Union[int, List[int], str] = ""
    port: Optional[int] = None
    path: Union[str, List[str]]
    query: Optional[str] = None
    fragment: Optional[str] = None

    # Indicates whether a color (:) separating a username from a password
    # existed in the parsed URL. This enables :func:`_serialize_url` to
    # generate a URL that matches the input URL, if desired.
    _password_token_seen: bool = False

    # Indicates, for an empty port component, whether or not a colon (:)
    # character was used. This enables :func:`_serialize_url` to
    # generate a URL that matches the input URL, if desired.
    _port_token_seen: bool = False

    # Indicates whether or not a default port was specified in the input URL.
    # This enables :func:`_serialize_url` to generate a URL that matches the
    # input URL, if desired.
    _default_port_seen: bool = False

    # Indicates, for an empty path component, whether or not a slash (/)
    # character was used. This enables :func:`_serialize_url` to
    # generate a URL that matches the input URL, if desired.
    _path_token_seen: bool = False

    def __init__(self) -> None:
        self.path = []
        self.is_special = False

    def has_opaque_path(self) -> bool:
        return isinstance(self.path, str)

    @property
    def scheme(self) -> str:
        return self._scheme

    @scheme.setter
    def scheme(self, value: str) -> None:
        self._scheme = value
        self.is_special = value in _SPECIAL_SCHEMES


_SCHEME_CHARS = _ASCII_ALPHANUMERIC + "+-."


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#shorten-a-urls-path
def _shorten_path(url: _URL) -> None:
    path = url.path
    if url.scheme == "file" and len(path) == 1 and _is_windows_drive_letter(path[0]):
        return
    url.path = path[:-1]


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#utf-8-percent-encode
# Extended to handled cases where % is to be percent-encoded.
def _percent_encode_after_encoding(
    input: str,
    *,
    encoding: str,
    percent_encode_set: _PercentEncodeSet,
    space_as_plus: bool = False,
) -> str:
    encoder = _get_encoder(encoding)
    output = ""
    # TODO: Use an alternative to xmlcharrefreplace that returns %26%23NNN%3B
    # instead of &#NNN;
    encode_output, _ = encoder(input, "xmlcharrefreplace")
    for i in range(len(encode_output)):  # pylint: disable=consider-using-enumerate
        byte = encode_output[i]
        if space_as_plus and byte == 0x20:
            output += "+"
            continue
        isomorph = chr(byte)
        if isomorph not in percent_encode_set:
            output += isomorph
        elif isomorph == "%":
            if (
                len(encode_output) <= i + 2
                or chr(encode_output[i + 1]) not in _ASCII_HEX_DIGIT
                or chr(encode_output[i + 2]) not in _ASCII_HEX_DIGIT
            ):
                output += "%25"
            else:
                output += "%"
        else:
            output += f"%{byte:02X}"

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

# constants from RFC 3986, Section 2.2 and 2.3
RFC3986_GEN_DELIMS = b":/?#[]@"
RFC3986_SUB_DELIMS = b"!$&'()*+,;="
RFC3986_RESERVED = RFC3986_GEN_DELIMS + RFC3986_SUB_DELIMS
RFC3986_UNRESERVED = (string.ascii_letters + string.digits + "-._~").encode("ascii")
EXTRA_SAFE_CHARS = b"|"  # see https://github.com/scrapy/w3lib/pull/25

RFC3986_USERINFO_SAFE_CHARS = RFC3986_UNRESERVED + RFC3986_SUB_DELIMS + b":"
_safe_chars = RFC3986_RESERVED + RFC3986_UNRESERVED + EXTRA_SAFE_CHARS + b"%"
_path_safe_chars = _safe_chars.replace(b"#", b"")

# Characters that are safe in all of:
#
# -   RFC 2396 + RFC 2732, as interpreted by Java 8’s java.net.URI class
# -   RFC 3986
# -   The URL living standard
#
# NOTE: % is currently excluded from these lists of characters, due to
# limitations of the current safe_url_string implementation, but it should also
# be escaped as %25 when it is not already being used as part of an escape
# character.
_USERINFO_SAFEST_CHARS = RFC3986_USERINFO_SAFE_CHARS.translate(None, delete=b":;=")
_PATH_SAFEST_CHARS = _safe_chars.translate(None, delete=b"#[]|")
_QUERY_SAFEST_CHARS = _PATH_SAFEST_CHARS
_SPECIAL_QUERY_SAFEST_CHARS = _PATH_SAFEST_CHARS.translate(None, delete=b"'")
_FRAGMENT_SAFEST_CHARS = _PATH_SAFEST_CHARS

_SAFE_USERINFO_PERCENT_ENCODE_SET = (
    _USERINFO_PERCENT_ENCODE_SET
    | _RFC3986_USERINFO_PERCENT_ENCODE_SET
    | _RFC2396_USERINFO_PERCENT_ENCODE_SET
)
_SAFE_PATH_PERCENT_ENCODE_SET = (
    _PATH_PERCENT_ENCODE_SET
    | _RFC3986_PATH_PERCENT_ENCODE_SET
    | _RFC2396_ABS_PATH_PERCENT_ENCODE_SET
)
_SAFE_QUERY_PERCENT_ENCODE_SET = (
    _QUERY_PERCENT_ENCODE_SET
    | _RFC3986_QUERY_PERCENT_ENCODE_SET
    | _RFC2396_QUERY_PERCENT_ENCODE_SET
)
_SAFE_SPECIAL_QUERY_PERCENT_ENCODE_SET = (
    _SPECIAL_QUERY_PERCENT_ENCODE_SET
    | _RFC3986_QUERY_PERCENT_ENCODE_SET
    | _RFC2396_QUERY_PERCENT_ENCODE_SET
)
_SAFE_FRAGMENT_PERCENT_ENCODE_SET = (
    _FRAGMENT_PERCENT_ENCODE_SET
    | _RFC3986_FRAGMENT_PERCENT_ENCODE_SET
    | _RFC2396_FRAGMENT_PERCENT_ENCODE_SET
)

# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#forbidden-host-code-point
_FORBIDDEN_HOST_CODE_POINTS = "\x00\t\n\r #/:<>?@[\\]^|"
_FORBIDDEN_DOMAIN_CODE_POINTS = _FORBIDDEN_HOST_CODE_POINTS + _C0_CONTROL + "%\x7F"


def _parse_ipv6(input: str) -> List[int]:
    address = [0] * 8
    piece_index = 0
    compress = None
    pointer = 0
    input_length = len(input)
    if pointer < input_length and input[pointer] == ":":
        if pointer + 1 >= input_length or input[pointer + 1] != ":":
            raise ValueError
        pointer += 2
        piece_index += 1
        compress = piece_index
    while pointer < input_length:
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
        while (
            length < 4 and pointer < input_length and input[pointer] in _ASCII_HEX_DIGIT
        ):
            value = value * 0x10 + int(input[pointer], base=16)
            pointer += 1
            length += 1
        if pointer < input_length and input[pointer] == ".":
            if length == 0:
                raise ValueError
            pointer -= length
            if piece_index > 6:
                raise ValueError
            numbers_seen = 0
            while pointer < input_length:
                ipv4_piece = None
                if numbers_seen > 0:
                    if input[pointer] == "." and numbers_seen < 4:
                        pointer += 1
                    else:
                        raise ValueError
                if pointer >= input_length or input[pointer] not in _ASCII_DIGIT:
                    raise ValueError
                while pointer < input_length and input[pointer] in _ASCII_DIGIT:
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
                assert isinstance(ipv4_piece, int)
                address[piece_index] = address[piece_index] * 0x100 + ipv4_piece
                numbers_seen += 1
                if numbers_seen in (2, 4):
                    piece_index += 1
            if numbers_seen != 4:
                raise ValueError
            break
        if pointer < input_length and input[pointer] == ":":
            pointer += 1
            if pointer >= input_length:
                raise ValueError
        elif pointer < input_length:
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
) -> str:
    return _percent_encode_after_encoding(
        input,
        encoding="utf-8",
        percent_encode_set=percent_encode_set,
    )


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-opaque-host-parser
def _parse_opaque_host(input: str) -> str:
    for code_point in input:
        if code_point in _FORBIDDEN_HOST_CODE_POINTS:
            raise ValueError
    return _utf_8_percent_encode(input, _C0_CONTROL_PERCENT_ENCODE_SET)


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#ipv4-number-parser
def _parse_ipv4_number(input: str) -> Tuple[int, bool]:
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
def _ends_in_number(input: str) -> bool:
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
def _parse_ipv4(input: str) -> int:
    parts = input.split(".")
    if parts and not parts[-1]:
        parts = parts[:-1]
    if len(parts) > 4:
        raise ValueError
    numbers = []
    for part in parts:
        result = _parse_ipv4_number(part)
        numbers.append(result[0])
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


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-domain-to-ascii
def _domain_to_ascii(domain: str, *, be_strict: bool = False) -> str:
    result = _utr46._to_ascii(
        domain,
        use_std3_ascii_rules=be_strict,
        check_hyphens=False,
        check_bidi=True,
        check_joiners=True,
        transitional_processing=False,
        verify_dns_length=be_strict,
    )
    if not result:
        raise ValueError(
            f"Domain name {domain!r} is an empty string after conversion to "
            f"ASCII, which makes for an invalid domain name."
        )
    return result


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#concept-host-parser
def _parse_host(
    input: str,
    *,
    is_special: bool = True,
) -> Union[str, int, List[int]]:
    if input.startswith("["):
        if not input.endswith("]"):
            raise ValueError
        return _parse_ipv6(input[1:-1])
    if not is_special:
        return _parse_opaque_host(input)
    domain = unquote(input)
    ascii_domain = _domain_to_ascii(domain)
    for code_point in ascii_domain:
        if code_point in _FORBIDDEN_DOMAIN_CODE_POINTS:
            raise ValueError
    if _ends_in_number(ascii_domain):
        return _parse_ipv4(ascii_domain)
    return ascii_domain


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#windows-drive-letter
def _is_windows_drive_letter(input: str) -> bool:
    return len(input) == 2 and input[0] in _ASCII_ALPHA and input[1] in ":|"


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#start-with-a-windows-drive-letter
def _starts_with_windows_drive_letter(input: str) -> bool:
    input_length = len(input)
    return (
        input_length >= 2
        and _is_windows_drive_letter(input[:2])
        and (input_length == 2 or input[2] in "/\\?#")
    )


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#double-dot-path-segment
def _is_double_dot_path_segment(input: str) -> bool:
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
def _is_single_dot_path_segment(input: str) -> bool:
    return input in (
        ".",
        "%2e",
        "%2E",
    )


# Wrapper for _utf_8_percent_encode that ensures that, if percent symbols need
# to be escaped, they are escaped in an idempotent way (i.e. if they are
# already part of an escape sequence, they are not re-encoded).
def _idempotent_utf_8_percent_encode(
    *, input: str, pointer: int, encode_set: _PercentEncodeSet
) -> str:
    code_point = input[pointer]
    if code_point == "%" and "%" in encode_set:
        if (
            pointer + 2 >= len(input)
            or input[pointer + 1] not in _ASCII_HEX_DIGIT
            or input[pointer + 2] not in _ASCII_HEX_DIGIT
        ):
            return "%25"
        return "%"
    return _utf_8_percent_encode(code_point, encode_set)


def _preprocess_url(url: str) -> str:
    return url.strip(_C0_CONTROL_OR_SPACE).translate(_ASCII_TAB_OR_NEWLINE_TRANSLATION_TABLE)


def _parse_url(
    input: str,
    *,
    base_url: str = None,
    encoding: str = "utf-8",
    userinfo_percent_encode_set: _PercentEncodeSet = _USERINFO_PERCENT_ENCODE_SET,
    path_percent_encode_set: _PercentEncodeSet = _PATH_PERCENT_ENCODE_SET,
    query_percent_encode_set: _PercentEncodeSet = _QUERY_PERCENT_ENCODE_SET,
    special_query_percent_encode_set: _PercentEncodeSet = _SPECIAL_QUERY_PERCENT_ENCODE_SET,
    fragment_percent_encode_set: _PercentEncodeSet = _FRAGMENT_PERCENT_ENCODE_SET,
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

    if base_url is not None:
        base = _parse_url(base_url, encoding=encoding)
    else:
        base = None
    encoding = _get_output_encoding(encoding)

    url = _URL()
    state = SCHEME_START
    buffer = ""
    at_sign_seen = inside_brackets = skip_authority_shortcut = False
    pointer = 0

    input = _preprocess_url(input)
    input_length = len(input)

    while True:
        reached_end: bint = pointer >= input_length
        if not reached_end:
            c: str = input[pointer]

        if state == SCHEME_START:
            if not reached_end and c in _ASCII_ALPHA:
                buffer += c
                state = SCHEME
            else:
                state = NO_SCHEME
                pointer -= 1

        elif state == SCHEME:
            if not reached_end and c in _SCHEME_CHARS:
                buffer += c
            elif not reached_end and c == ":":
                url.scheme = buffer.lower()
                buffer = ""
                if url.scheme == "file":
                    state = FILE
                elif url.is_special:
                    if base is not None and base.scheme == url.scheme:
                        state = SPECIAL_RELATIVE_OR_AUTHORITY
                    else:
                        state = SPECIAL_AUTHORITY_SLASHES
                elif pointer + 1 < len(input) and input[pointer + 1] == "/":
                    state = PATH_OR_AUTHORITY
                    pointer += 1
                else:
                    url.path = ""
                    state = OPAQUE_PATH
            else:
                buffer = ""
                state = NO_SCHEME
                pointer = -1

        elif state == NO_SCHEME:
            if base is None:
                raise ValueError
            if base.has_opaque_path():
                if not reached_end and c != "#":
                    raise ValueError
                url.scheme = base.scheme
                url.path = base.path
                url.query = base.query
                url.fragment = ""
                state = FRAGMENT
            else:
                if base.scheme != "file":
                    state = RELATIVE
                else:
                    state = FILE
                pointer -= 1

        elif state == SPECIAL_RELATIVE_OR_AUTHORITY:
            if not reached_end and c == "/" and pointer + 1 < input_length and input[pointer + 1] == "/":
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
                pointer += 1
            else:
                state = RELATIVE
                pointer -= 1

        elif state == PATH_OR_AUTHORITY:
            if not reached_end and c == "/":
                state = AUTHORITY
            else:
                state = PATH
                pointer -= 1

        elif state == RELATIVE:
            url.scheme = base.scheme
            if not reached_end and (c == "/" or url.is_special and c == "\\"):
                state = RELATIVE_SLASH
            else:
                url.username = base.username
                url.password = base.password
                url.hostname = base.hostname
                url.port = base.port
                url.path = base.path
                url.query = base.query
                if not reached_end and c == "?":
                    url.query = ""
                    state = QUERY
                elif not reached_end and c == "#":
                    url.fragment = ""
                    state = FRAGMENT
                elif not reached_end:
                    url.query = None
                    _shorten_path(url)
                    state = PATH
                    pointer -= 1

        elif state == RELATIVE_SLASH:
            if url.is_special and not reached_end and c in "/\\":
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
            elif not reached_end and c == "/":
                state = AUTHORITY
            else:
                url.username = base.username
                url.password = base.password
                url.hostname = base.hostname
                url.port = base.port
                state = PATH
                pointer -= 1

        elif state == SPECIAL_AUTHORITY_SLASHES:
            if not reached_end and c == "/" and pointer + 1 < input_length and input[pointer + 1] == "/":
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
                pointer += 1
            else:
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
                pointer -= 1

        elif state == SPECIAL_AUTHORITY_IGNORE_SLASHES:
            if reached_end or c not in "/\\":
                state = AUTHORITY
                pointer -= 1

        elif state == AUTHORITY:
            if not skip_authority_shortcut:
                at_sign_index = input.find("@", pointer)
                if at_sign_index == -1:
                    state = HOST
                else:
                    skip_authority_shortcut = True
                pointer -= 1
            elif not reached_end and c == "@":
                if at_sign_seen:
                    buffer = "%40" + buffer
                at_sign_seen = True
                for i, code_point in enumerate(buffer):
                    if code_point == ":" and not url._password_token_seen:
                        url._password_token_seen = True
                        continue
                    encoded_code_points = _idempotent_utf_8_percent_encode(
                        input=buffer,
                        pointer=i,
                        encode_set=userinfo_percent_encode_set,
                    )
                    if url._password_token_seen:
                        url.password += encoded_code_points
                    else:
                        url.username += encoded_code_points
                buffer = ""
            elif reached_end or c in "/?#" or url.is_special and c == "\\":
                if at_sign_seen and not buffer:
                    raise ValueError
                pointer -= len(buffer) + 1
                buffer = ""
                state = HOST
            else:
                buffer += c

        elif state == HOST:
            if not reached_end and c == ":" and not inside_brackets:
                if not buffer:
                    raise ValueError
                host = _parse_host(buffer, is_special=url.is_special)
                url.hostname = host
                buffer = ""
                state = PORT
                url._port_token_seen = True
            elif reached_end or c in "/?#" or url.is_special and c == "\\":
                pointer -= 1
                if url.is_special and not buffer:
                    raise ValueError
                host = _parse_host(buffer, is_special=url.is_special)
                url.hostname = host
                buffer = ""
                state = PATH_START
            elif not reached_end:
                if c == "[":
                    inside_brackets = True
                elif c == "]":
                    inside_brackets = False
                buffer += c

        elif state == PORT:
            if not reached_end and c in _ASCII_DIGIT:
                buffer += c
            elif reached_end or c in "/?#" or url.is_special and c == "\\":
                if buffer:
                    port = int(buffer)
                    if port > 2**16 - 1:
                        raise ValueError
                    url.port = None if _DEFAULT_PORTS.get(url.scheme) == port else port
                    url._default_port_seen = url.port is None
                    buffer = ""
                state = PATH_START
                pointer -= 1
            else:
                raise ValueError

        elif state == FILE:
            url.scheme = "file"
            url.hostname = ""
            if not reached_end and c in "/\\":
                state = FILE_SLASH
            elif base is not None and base.scheme == "file":
                url.hostname = base.hostname
                url.path = base.path
                url.query = base.query
                if not reached_end and c == "?":
                    url.query = ""
                    state = QUERY
                elif not reached_end and c == "#":
                    url.fragment = ""
                    state = FRAGMENT
                elif not reached_end:
                    url.query = None
                    if not _starts_with_windows_drive_letter(input[pointer:]):
                        _shorten_path(url)
                    else:
                        url.path = []
                    state = PATH
                    pointer -= 1
            else:
                state = PATH
                pointer -= 1

        elif state == FILE_SLASH:
            if not reached_end and c in "/\\":
                state = FILE_HOST
            else:
                if base is not None and base.scheme == "file":
                    url.hostname = base.hostname
                    if not _starts_with_windows_drive_letter(
                        input[pointer:]
                    ) and _is_windows_drive_letter(base.path[0]):
                        url.path.append(base.path[0])
                state = PATH
                pointer -= 1

        elif state == FILE_HOST:
            if reached_end or c in "/\\?#":
                pointer -= 1
                if _is_windows_drive_letter(buffer):
                    state = PATH
                elif not buffer:
                    url.hostname = ""
                    state = PATH_START
                else:
                    host = _parse_host(buffer, is_special=url.is_special)
                    if host == "localhost":
                        host = ""
                    url.hostname = host
                    buffer = ""
                    state = PATH_START
            elif not reached_end:
                buffer += c

        elif state == PATH_START:
            if url.is_special:
                state = PATH
                if not reached_end and c not in "/\\":
                    pointer -= 1
            elif not reached_end:
                if c == "?":
                    url.query = ""
                    state = QUERY
                elif c == "#":
                    url.fragment = ""
                    state = FRAGMENT
                else:
                    state = PATH
                    if c != "/":
                        pointer -= 1

        elif state == PATH:
            if reached_end or c == "/" or (url.is_special and c == "\\") or c in "?#":
                if _is_double_dot_path_segment(buffer):
                    _shorten_path(url)
                    if c != "/" and not (url.is_special and c == "\\"):
                        url.path.append("")
                elif _is_single_dot_path_segment(buffer):
                    if c != "/" and not (url.is_special and c == "\\"):
                        url.path.append("")
                else:
                    if (
                        url.scheme == "file"
                        and not url.path
                        and _is_windows_drive_letter(buffer)
                    ):
                        buffer = buffer[0] + ":" + buffer[2:]
                    if (
                        not url.path
                        and not buffer
                        and not reached_end
                        and c in "?#"
                        and input[pointer - 1] not in "/\\"
                    ):
                        url._path_token_seen = True
                    url.path.append(buffer)
                buffer = ""
                if not reached_end:
                    if c == "?":
                        url.query = ""
                        state = QUERY
                    elif c == "#":
                        url.fragment = ""
                        state = FRAGMENT
            else:
                buffer += _idempotent_utf_8_percent_encode(
                    input=input,
                    pointer=pointer,
                    encode_set=path_percent_encode_set,
                )

        elif state == OPAQUE_PATH:
            if not reached_end:
                if c == "?":
                    url.query = ""
                    state = QUERY
                elif c == "#":
                    url.fragment = ""
                    state = FRAGMENT
                else:
                    encoded = _utf_8_percent_encode(
                        c,
                        _C0_CONTROL_PERCENT_ENCODE_SET,
                    )
                    url.path += encoded

        elif state == QUERY:
            if encoding != "utf-8" and (
                not url.is_special or url.scheme in ("ws", "wss")
            ):
                encoding = "utf-8"
            if reached_end or c == "#":
                percent_encode_set = (
                    special_query_percent_encode_set
                    if url.is_special
                    else query_percent_encode_set
                )
                url.query += _percent_encode_after_encoding(
                    buffer,
                    encoding=encoding,
                    percent_encode_set=percent_encode_set,
                )
                buffer = ""
                if not reached_end and c == "#":
                    url.fragment = ""
                    state = FRAGMENT
            elif not reached_end:
                buffer += c

        elif state == FRAGMENT:
            if not reached_end:
                url.fragment += _idempotent_utf_8_percent_encode(
                    input=input, pointer=pointer, encode_set=fragment_percent_encode_set
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


def _get_ipv6_first_longest_0_piece_index(
    address: List[int], *, min_length: int = 2
) -> Optional[int]:
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
def _serialize_host(host: Union[str, int, List[int]]) -> str:
    if isinstance(host, int):
        return _serialize_ipv4(host)
    if isinstance(host, list):
        return f"[{_serialize_ipv6(host)}]"
    return host


# https://url.spec.whatwg.org/commit-snapshots/a46cb9188a48c2c9d80ba32a9b1891652d6b4900/#url-path-serializer
def _serialize_url_path(url: _URL, *, canonicalize: bool = None) -> str:
    if url.has_opaque_path():
        assert isinstance(url.path, str)
        return url.path
    if len(url.path) <= 1 and url._path_token_seen and not canonicalize:
        return ""
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
    if url.hostname is not None:
        output += "//"
        if url.username or url.password:
            output += url.username
            if url.password:
                output += f":{url.password}"
            elif not canonicalize and url._password_token_seen:
                output += ":"
            output += "@"
        output += _serialize_host(url.hostname)
        if url.port is not None:
            output += f":{url.port}"
        elif not canonicalize:
            if url._default_port_seen:
                output += f":{_DEFAULT_PORTS[url.scheme]}"
            elif url._port_token_seen:
                output += ":"
    elif not url.has_opaque_path() and len(url.path) > 1 and not url.path[0]:
        output += "/."
    output += _serialize_url_path(url, canonicalize=canonicalize)
    if url.query is not None:
        output += f"?{url.query}"
    if not exclude_fragment and url.fragment is not None:
        output += f"#{url.fragment}"
    return output


def _safe_url(input: str, encoding: str) -> str:
    url = _parse_url(
        input,
        encoding=encoding,
        userinfo_percent_encode_set=_SAFE_USERINFO_PERCENT_ENCODE_SET,
        path_percent_encode_set=_SAFE_PATH_PERCENT_ENCODE_SET,
        query_percent_encode_set=_SAFE_QUERY_PERCENT_ENCODE_SET,
        special_query_percent_encode_set=_SAFE_SPECIAL_QUERY_PERCENT_ENCODE_SET,
        fragment_percent_encode_set=_SAFE_FRAGMENT_PERCENT_ENCODE_SET,
    )
    return _serialize_url(url, canonicalize=False)
