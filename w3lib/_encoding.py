# https://encoding.spec.whatwg.org/

import codecs
from collections import deque
from typing import AnyStr, Callable, Dict, List, Optional, Tuple, Union

from ._infra import _ASCII_WHITESPACE


CodecFunction = Callable[[AnyStr], Tuple[AnyStr, int]]
DecodeFunction = Callable[[bytes], Tuple[str, int]]
EncodeFunction = Callable[[str], Tuple[bytes, int]]


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


class _PotentialError:
    def __init__(
        self,
        *,
        _continue: bool = False,
        error: bool = False,
        error_code_point: Union[bytes, str, None] = None,
        finished: bool = False,
        items: Union[bytes, str, None] = None,
    ) -> None:
        self.code_point: Union[bytes, str, None] = error_code_point
        self._continue = _continue
        self._error = error
        self._finished = finished
        if isinstance(items, bytes):
            _items: List[Union[bytes, str]] = [b"%c" % byte for byte in items]
        elif items is not None:
            _items = list(items)
        else:
            _items = []
        self.items: List[Union[bytes, str]] = _items

    def is_continue(self) -> bool:
        return self._continue

    def is_finished(self) -> bool:
        return self._finished

    def is_error(self) -> bool:
        return self._error


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#handler
def _handle_codec(
    *, codec: CodecFunction, item: Union[bytes, str, None]
) -> _PotentialError:
    if item is None:
        return _PotentialError(finished=True)
    try:
        items, _ = codec(item)
    except UnicodeError:
        return _PotentialError(error=True, error_code_point=item)
    else:
        if items:
            return _PotentialError(items=items)
        else:
            return _PotentialError(_continue=True)


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#concept-stream-read
def _read(input: deque) -> Union[bytes, str, None]:
    if not input:
        return None
    return input.popleft()


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#concept-encoding-process
def _process_item(
    item: Union[bytes, str, None], *, codec: CodecFunction, output: deque, mode: str
) -> _PotentialError:
    result = _handle_codec(codec=codec, item=item)
    if result.is_finished():
        return result
    if result.items:
        for result_item in result.items:
            output.append(result_item)
    elif result.is_error():
        assert result.code_point is not None
        if mode == "replacement":
            output.append("\uFFFD")
        elif mode == "html":
            output.append(b"&#%i;" % ord(result.code_point))
        elif mode == "fatal":
            return result
    return _PotentialError(_continue=True)


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#utf-8-decode-without-bom-or-fail
def _utf_8_decode_without_bom_or_fail(
    *,
    input: deque,
    output: Optional[deque] = None,
) -> deque:
    if output is None:
        output = deque()
    potential_error = _process_queue(
        input=input,
        output=output,
        codec=_UTF_8_DECODER,
        error_mode="fatal",
    )
    if potential_error.is_error():
        raise ValueError
    return output


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#concept-encoding-run
def _process_queue(
    *,
    input: deque,
    codec: CodecFunction,
    output: deque,
    error_mode: str,
) -> _PotentialError:
    while True:
        result = _process_item(
            _read(input),
            codec=codec,
            output=output,
            mode=error_mode,
        )
        if not result.is_continue():
            return result


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#encode-or-fail
def _encode_or_fail(
    *, input: deque, encoder: EncodeFunction, output: deque
) -> Optional[_PotentialError]:
    potential_error = _process_queue(
        input=input,
        codec=encoder,
        output=output,
        error_mode="fatal",
    )
    if potential_error.is_error():
        return potential_error
    return None


def _get_decoder(encoding: str) -> DecodeFunction:
    codec_info = codecs.lookup(encoding)
    return codec_info.decode


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#get-an-encoder
def _get_encoder(encoding: str) -> EncodeFunction:
    codec_info = codecs.lookup(encoding)
    return codec_info.encode


_UTF_8_DECODER = _get_decoder("utf-8")
_UTF_8_ENCODER = _get_encoder("utf-8")


# https://encoding.spec.whatwg.org/commit-snapshots/3721bec25c59f5506744dfeb8e3af7783e2f0f52/#concept-encoding-get
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
def _get_output_encoding(encoding: str) -> str:
    encoding = _get_encoding(encoding)
    if encoding in _OUTPUT_ENCODING_UTF8_ENCODINGS:
        return _UTF_8_ENCODING
    return encoding
