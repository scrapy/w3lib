# https://encoding.spec.whatwg.org/

import codecs
from functools import cache
from typing import AnyStr, Callable, Dict, Tuple

from ._infra import _ASCII_WHITESPACE


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
@cache
def _get_encoder(encoding: str) -> EncodeFunction:
    codec_info = codecs.lookup(encoding)
    return codec_info.encode


_UTF_8_ENCODER = _get_encoder("utf-8")


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#concept-encoding-get
@cache
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
@cache
def _get_output_encoding(encoding: str) -> str:
    encoding = _get_encoding(encoding)
    if encoding in _OUTPUT_ENCODING_UTF8_ENCODINGS:
        return _UTF_8_ENCODING
    return encoding
