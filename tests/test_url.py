import json
import os
import unittest
from collections import deque
from collections.abc import Iterator
from itertools import tee
from pathlib import Path
from platform import python_implementation
from timeit import timeit
from urllib.parse import urlparse

import pytest

from w3lib._infra import (
    _ASCII_ALPHA,
    _ASCII_ALPHANUMERIC,
    _ASCII_TAB_OR_NEWLINE,
    _C0_CONTROL_OR_SPACE,
)
from w3lib._url import (
    _C0_CONTROL_PERCENT_ENCODE_SET,
    _domain_to_ascii,
    _parse_url,
    _percent_encode_after_encoding,
    _serialize_host,
    # _serialize_url,
    _serialize_url_path,
    _SPECIAL_QUERY_PERCENT_ENCODE_SET,
    _SPECIAL_SCHEMES,
)
from w3lib.url import (
    add_or_replace_parameter,
    add_or_replace_parameters,
    any_to_uri,
    canonicalize_url,
    file_uri_to_path,
    is_url,
    parse_data_uri,
    parse_url,
    path_to_file_uri,
    safe_download_url,
    safe_url,
    safe_url_string,
    url_query_parameter,
    url_query_cleaner,
)


TO_ASCII_TEST_DATA_FILE_PATH = Path(__file__).parent / "to-ascii-test-data.json"
TO_ASCII_TEST_DATA_KNOWN_ISSUES = (
    # TODO: Investigate.
    "xn--a-yoc",
    "a%C2%ADb",
    "%C2%AD",
)

with open(TO_ASCII_TEST_DATA_FILE_PATH, encoding="utf-8") as input:
    TO_ASCII_TEST_DATA = json.load(input)


@pytest.mark.parametrize(
    "input,output",
    (
        case
        if case[0] not in TO_ASCII_TEST_DATA_KNOWN_ISSUES
        else pytest.param(*case, marks=pytest.mark.xfail(strict=True))
        for case in (
            (
                i["input"],
                i["output"],
            )
            for i in TO_ASCII_TEST_DATA
            if not isinstance(i, str)
        )
    ),
)
def test_domain_to_ascii(input, output):
    if output is not None:
        assert _domain_to_ascii(input) == output
        return
    with pytest.raises(ValueError):
        _domain_to_ascii(input)


URL_TEST_DATA_FILE_PATH = Path(__file__).parent / "url-test-data.json"
URL_TEST_DATA_KNOWN_ISSUES = (
    # https://github.com/web-platform-tests/wpt/issues/37010
    "http://example.com/\ud800\U000107fe\udfff\ufdd0\ufdcf\ufdefﷰ\ufffe\uffff?\ud800\U000107fe\udfff\ufdd0\ufdcf\ufdefﷰ\ufffe\uffff",
)

with open(URL_TEST_DATA_FILE_PATH, encoding="utf-8") as input:
    URL_TEST_DATA = json.load(input)


@pytest.mark.parametrize(
    "input,base,failure,href,protocol,username,password,hostname,port,pathname,search,hash",
    (
        case
        if case[0] not in URL_TEST_DATA_KNOWN_ISSUES
        else pytest.param(*case, marks=pytest.mark.xfail(strict=True))
        for case in (
            (
                i["input"],
                i["base"],
                i.get("failure"),
                i.get("href"),
                i.get("protocol"),
                i.get("username"),
                i.get("password"),
                i.get("hostname"),
                i.get("port"),
                i.get("pathname"),
                i.get("search"),
                i.get("hash"),
            )
            for i in URL_TEST_DATA
            if not isinstance(i, str)
        )
    ),
)
def test_parse_url(
    input,
    base,
    failure,
    href,
    protocol,
    username,
    password,
    hostname,
    port,
    pathname,
    search,
    hash,
):
    if failure:
        with pytest.raises(ValueError):
            _parse_url(input, base_url=base)
        return

    url = _parse_url(input, base_url=base)
    assert url.scheme == (protocol[:-1] if protocol else None)
    assert url.username == username
    assert url.password == password
    assert _serialize_host(url.hostname) == hostname
    assert url.port == (None if not port else int(port))
    # TODO: Find out why we do not always get right whether path is supposed to
    # be / or an empty string.
    assert (_serialize_url_path(url) or "/") == (pathname or "/")
    # TODO: Find out why we do not always get right whether query is supposed
    # to be an empty string or None.
    assert (url.query or "") == (search[1:] if search else "")
    # TODO: Find out why we do not always get right whether fragment is
    # supposed to be an empty string or None.
    assert (url.fragment or "") == (hash[1:] if hash else "")
    # TODO: Address the TODOs above.
    # assert _serialize_url(url) == href


PERCENT_ENCODE_TEST_DATA_FILE_PATH = (
    Path(__file__).parent / "percent-encoding-test-data.json"
)
PERCENT_ENCODE_TEST_DATA_KNOWN_ISSUES = {
    # TODO: Investigate.
    ("\x0eA", "iso-2022-jp"),
    ("\ue5e5", "gb18030"),
}

with open(PERCENT_ENCODE_TEST_DATA_FILE_PATH, encoding="utf-8") as input:
    PERCENT_ENCODE_TEST_DATA = json.load(input)


@pytest.mark.parametrize(
    "input,output,encoding,percent_encode_set",
    (
        ("", "", "utf-8", _C0_CONTROL_PERCENT_ENCODE_SET),
        ("a", "a", "utf-8", _C0_CONTROL_PERCENT_ENCODE_SET),
        *(
            (input, output, encoding, _SPECIAL_QUERY_PERCENT_ENCODE_SET)
            if (input, encoding) not in PERCENT_ENCODE_TEST_DATA_KNOWN_ISSUES
            else pytest.param(
                input,
                output,
                encoding,
                _SPECIAL_QUERY_PERCENT_ENCODE_SET,
                marks=pytest.mark.xfail(strict=True),
            )
            for input, _output in (
                (
                    i["input"],
                    i["output"],
                )
                for i in PERCENT_ENCODE_TEST_DATA
                if not isinstance(i, str)
            )
            for encoding, output in _output.items()
        ),
    ),
)
def test_percent_encode_after_encoding(input, output, encoding, percent_encode_set):
    actual = _percent_encode_after_encoding(
        input,
        encoding=encoding,
        percent_encode_set=percent_encode_set,
    )
    assert actual == output


UNSET = object()

# Test cases for URL-to-safe-URL conversions with a URL and an encoding as
# input parameters.
#
# (encoding, input URL, output URL or exception)
SAFE_URL_ENCODING_CASES = (
    (UNSET, "", ValueError),
    (UNSET, "https://example.com", "https://example.com"),
    (UNSET, "https://example.com/©", "https://example.com/%C2%A9"),
    # Paths are always UTF-8-encoded.
    ("iso-8859-1", "https://example.com/©", "https://example.com/%C2%A9"),
    # Queries are UTF-8-encoded if the scheme is not special, ws or wss.
    ("iso-8859-1", "a://example.com?©", "a://example.com?%C2%A9"),
    *(
        ("iso-8859-1", f"{scheme}://example.com?©", f"{scheme}://example.com?%C2%A9")
        for scheme in ("ws", "wss")
    ),
    *(
        ("iso-8859-1", f"{scheme}://example.com?©", f"{scheme}://example.com?%A9")
        for scheme in _SPECIAL_SCHEMES
        if scheme not in {"ws", "wss"}
    ),
    # Fragments are always UTF-8-encoded.
    ("iso-8859-1", "https://example.com#©", "https://example.com#%C2%A9"),
)

INVALID_SCHEME_FOLLOW_UPS = "".join(
    chr(value)
    for value in range(0x81)
    if (
        chr(value) not in _ASCII_ALPHANUMERIC
        and chr(value) not in "+-."
        and chr(value) not in _C0_CONTROL_OR_SPACE  # stripped
        and chr(value) != ":"  # separator
    )
)

SAFE_URL_URL_INVALID_SCHEME_CASES = tuple(
    (f"{scheme}://example.com", ValueError)
    for scheme in (
        # A scheme is required.
        "",
        # The first scheme letter must be an ASCII alpha.
        # Note: 0x80 is included below to also test non-ASCII example.
        *(
            chr(value)
            for value in range(0x81)
            if (
                chr(value) not in _ASCII_ALPHA
                and chr(value) not in _C0_CONTROL_OR_SPACE  # stripped
                and chr(value) != ":"  # separator
            )
        ),
        # The follow-up scheme letters can also be ASCII numbers, plus, hyphen,
        # or period.
        f"a{INVALID_SCHEME_FOLLOW_UPS}",
    )
)

# Remove any leading and trailing C0 control or space from input.
SAFE_URL_URL_STRIP_CASES = tuple(
    (f"{char}https://example.com{char}", "https://example.com")
    for char in _C0_CONTROL_OR_SPACE
    if char not in _ASCII_TAB_OR_NEWLINE
)

SCHEME_NON_FIRST = _ASCII_ALPHANUMERIC + "+-."

# Username and password characters that do not need escaping.
# Removed for RFC 2396 and RFC 3986: %
# Removed for the URL living standard: :;=
USERINFO_SAFE = _ASCII_ALPHANUMERIC + "-_.!~*'()" + "&+$,"
USERNAME_TO_ENCODE = "".join(
    chr(value)
    for value in range(0x80)
    if (
        chr(value) not in _C0_CONTROL_OR_SPACE
        and chr(value) not in USERINFO_SAFE
        and chr(value) not in ":/?#\\"
    )
)
USERNAME_ENCODED = "".join(f"%{ord(char):02X}" for char in USERNAME_TO_ENCODE)
PASSWORD_TO_ENCODE = USERNAME_TO_ENCODE + ":"
PASSWORD_ENCODED = "".join(f"%{ord(char):02X}" for char in PASSWORD_TO_ENCODE)

# Path characters that do not need escaping.
# Removed for RFC 2396 and RFC 3986: %[\]^|
PATH_SAFE = _ASCII_ALPHANUMERIC + "-_.!~*'()" + ":@&=+$," + "/" + ";"
PATH_TO_ENCODE = "".join(
    chr(value)
    for value in range(0x80)
    if (
        chr(value) not in _C0_CONTROL_OR_SPACE
        and chr(value) not in PATH_SAFE
        and chr(value) not in "?#\\"
    )
)
PATH_ENCODED = "".join(f"%{ord(char):02X}" for char in PATH_TO_ENCODE)

# Query characters that do not need escaping.
# Removed for RFC 2396 and RFC 3986: %[\]^`{|}
# Removed for the URL living standard: ' (special)
QUERY_SAFE = _ASCII_ALPHANUMERIC + "-_.!~*'()" + ":@&=+$," + "/" + ";" + "?"
QUERY_TO_ENCODE = "".join(
    chr(value)
    for value in range(0x80)
    if (
        chr(value) not in _C0_CONTROL_OR_SPACE
        and chr(value) not in QUERY_SAFE
        and chr(value) not in "#"
    )
)
QUERY_ENCODED = "".join(f"%{ord(char):02X}" for char in QUERY_TO_ENCODE)
SPECIAL_QUERY_SAFE = QUERY_SAFE.replace("'", "")
SPECIAL_QUERY_TO_ENCODE = "".join(
    chr(value)
    for value in range(0x80)
    if (
        chr(value) not in _C0_CONTROL_OR_SPACE
        and chr(value) not in SPECIAL_QUERY_SAFE
        and chr(value) not in "#"
    )
)
SPECIAL_QUERY_ENCODED = "".join(f"%{ord(char):02X}" for char in SPECIAL_QUERY_TO_ENCODE)

# Fragment characters that do not need escaping.
# Removed for RFC 2396 and RFC 3986: #%[\\]^{|}
FRAGMENT_SAFE = _ASCII_ALPHANUMERIC + "-_.!~*'()" + ":@&=+$," + "/" + ";" + "?"
FRAGMENT_TO_ENCODE = "".join(
    chr(value)
    for value in range(0x80)
    if (chr(value) not in _C0_CONTROL_OR_SPACE and chr(value) not in FRAGMENT_SAFE)
)
FRAGMENT_ENCODED = "".join(f"%{ord(char):02X}" for char in FRAGMENT_TO_ENCODE)


# Test cases for URL-to-safe-URL conversions with only a URL as input parameter
# (i.e. no encoding or base URL).
#
# (input URL, output URL or exception)
SAFE_URL_URL_CASES = (
    # Invalid input type
    (1, Exception),
    (object(), Exception),
    # Empty string
    ("", ValueError),
    *SAFE_URL_URL_STRIP_CASES,
    # Remove all ASCII tab or newline from input.
    (
        (
            f"{_ASCII_TAB_OR_NEWLINE}h{_ASCII_TAB_OR_NEWLINE}ttps"
            f"{_ASCII_TAB_OR_NEWLINE}:{_ASCII_TAB_OR_NEWLINE}/"
            f"{_ASCII_TAB_OR_NEWLINE}/{_ASCII_TAB_OR_NEWLINE}a"
            f"{_ASCII_TAB_OR_NEWLINE}b{_ASCII_TAB_OR_NEWLINE}:"
            f"{_ASCII_TAB_OR_NEWLINE}a{_ASCII_TAB_OR_NEWLINE}b"
            f"{_ASCII_TAB_OR_NEWLINE}@{_ASCII_TAB_OR_NEWLINE}exam"
            f"{_ASCII_TAB_OR_NEWLINE}ple.com{_ASCII_TAB_OR_NEWLINE}:"
            f"{_ASCII_TAB_OR_NEWLINE}1{_ASCII_TAB_OR_NEWLINE}2"
            f"{_ASCII_TAB_OR_NEWLINE}/{_ASCII_TAB_OR_NEWLINE}a"
            f"{_ASCII_TAB_OR_NEWLINE}b{_ASCII_TAB_OR_NEWLINE}?"
            f"{_ASCII_TAB_OR_NEWLINE}a{_ASCII_TAB_OR_NEWLINE}b"
            f"{_ASCII_TAB_OR_NEWLINE}#{_ASCII_TAB_OR_NEWLINE}a"
            f"{_ASCII_TAB_OR_NEWLINE}b{_ASCII_TAB_OR_NEWLINE}"
        ),
        "https://ab:ab@example.com:12/ab?ab#ab",
    ),
    # Scheme
    (f"{_ASCII_ALPHA}://example.com", f"{_ASCII_ALPHA.lower()}://example.com"),
    (
        f"a{SCHEME_NON_FIRST}://example.com",
        f"a{SCHEME_NON_FIRST.lower()}://example.com",
    ),
    *SAFE_URL_URL_INVALID_SCHEME_CASES,
    # Authority
    ("https://a@example.com", "https://a@example.com"),
    ("https://a:@example.com", "https://a:@example.com"),
    ("https://a:a@example.com", "https://a:a@example.com"),
    ("https://a%3A@example.com", "https://a%3A@example.com"),
    (
        f"https://{USERINFO_SAFE}:{USERINFO_SAFE}@example.com",
        f"https://{USERINFO_SAFE}:{USERINFO_SAFE}@example.com",
    ),
    (
        f"https://{USERNAME_TO_ENCODE}:{PASSWORD_TO_ENCODE}@example.com",
        f"https://{USERNAME_ENCODED}:{PASSWORD_ENCODED}@example.com",
    ),
    ("https://@\\example.com", ValueError),
    ("https://\x80:\x80@example.com", "https://%C2%80:%C2%80@example.com"),
    # Host
    ("https://example.com", "https://example.com"),
    ("https://.example", "https://.example"),
    ("https://\x80.example", ValueError),
    ("https://%80.example", ValueError),
    # The 4 cases below test before and after crossing DNS length limits on
    # domain name labels (63 characters) and the domain name as a whole (253
    # characters). However, all cases are expected to pass because the URL
    # living standard does not require domain names to be within these limits.
    (f"https://{'a'*63}.example", f"https://{'a'*63}.example"),
    (f"https://{'a'*64}.example", f"https://{'a'*64}.example"),
    (
        f"https://{'a'*63}.{'a'*63}.{'a'*63}.{'a'*53}.example",
        f"https://{'a'*63}.{'a'*63}.{'a'*63}.{'a'*53}.example",
    ),
    (
        f"https://{'a'*63}.{'a'*63}.{'a'*63}.{'a'*54}.example",
        f"https://{'a'*63}.{'a'*63}.{'a'*63}.{'a'*54}.example",
    ),
    ("https://ñ.example", "https://xn--ida.example"),
    ("http://192.168.0.0", "http://192.168.0.0"),
    ("http://192.168.0.256", ValueError),
    ("http://192.168.0.0.0", ValueError),
    ("http://[2a01:5cc0:1:2::4]", "http://[2a01:5cc0:1:2::4]"),
    ("http://[2a01:5cc0:1:2:3:4]", ValueError),
    # Port
    ("https://example.com:", "https://example.com:"),
    ("https://example.com:1", "https://example.com:1"),
    ("https://example.com:443", "https://example.com:443"),
    # Path
    ("https://example.com/", "https://example.com/"),
    ("https://example.com/a", "https://example.com/a"),
    ("https://example.com\\a", "https://example.com/a"),
    ("https://example.com/a\\b", "https://example.com/a/b"),
    (
        f"https://example.com/{PATH_SAFE}",
        f"https://example.com/{PATH_SAFE}",
    ),
    (
        f"https://example.com/{PATH_TO_ENCODE}",
        f"https://example.com/{PATH_ENCODED}",
    ),
    ("https://example.com/ñ", "https://example.com/%C3%B1"),
    ("https://example.com/ñ%C3%B1", "https://example.com/%C3%B1%C3%B1"),
    # Query
    ("https://example.com?", "https://example.com?"),
    ("https://example.com/?", "https://example.com/?"),
    ("https://example.com?a", "https://example.com?a"),
    ("https://example.com?a=", "https://example.com?a="),
    ("https://example.com?a=b", "https://example.com?a=b"),
    (
        f"a://example.com?{QUERY_SAFE}",
        f"a://example.com?{QUERY_SAFE}",
    ),
    (
        f"a://example.com?{QUERY_TO_ENCODE}",
        f"a://example.com?{QUERY_ENCODED}",
    ),
    *(
        (
            f"{scheme}://example.com?{SPECIAL_QUERY_SAFE}",
            f"{scheme}://example.com?{SPECIAL_QUERY_SAFE}",
        )
        for scheme in _SPECIAL_SCHEMES
    ),
    *(
        (
            f"{scheme}://example.com?{SPECIAL_QUERY_TO_ENCODE}",
            f"{scheme}://example.com?{SPECIAL_QUERY_ENCODED}",
        )
        for scheme in _SPECIAL_SCHEMES
    ),
    ("https://example.com?ñ", "https://example.com?%C3%B1"),
    ("https://example.com?ñ%C3%B1", "https://example.com?%C3%B1%C3%B1"),
    # Fragment
    ("https://example.com#", "https://example.com#"),
    ("https://example.com/#", "https://example.com/#"),
    ("https://example.com?#", "https://example.com?#"),
    ("https://example.com/?#", "https://example.com/?#"),
    ("https://example.com#a", "https://example.com#a"),
    (
        f"a://example.com#{FRAGMENT_SAFE}",
        f"a://example.com#{FRAGMENT_SAFE}",
    ),
    (
        f"a://example.com#{FRAGMENT_TO_ENCODE}",
        f"a://example.com#{FRAGMENT_ENCODED}",
    ),
    ("https://example.com#ñ", "https://example.com#%C3%B1"),
    ("https://example.com#ñ%C3%B1", "https://example.com#%C3%B1%C3%B1"),
    # All fields, UTF-8 wherever possible.
    (
        "https://ñ:ñ@ñ.example:1/ñ?ñ#ñ",
        "https://%C3%B1:%C3%B1@xn--ida.example:1/%C3%B1?%C3%B1#%C3%B1",
    ),
)


def _test_safe_url_func(url, *, encoding=UNSET, output, func):
    kwargs = {}
    if encoding is not UNSET:
        kwargs["encoding"] = encoding
    try:
        is_exception = issubclass(output, Exception)
    except TypeError:
        is_exception = False
    if is_exception:
        with pytest.raises(output):
            func(url, **kwargs)
        return
    actual = func(url, **kwargs)
    assert actual == output
    assert func(actual, **kwargs) == output  # Idempotency


def _test_safe_url(url, *, encoding=UNSET, output):
    _test_safe_url_func(
        url,
        encoding=encoding,
        output=output,
        func=safe_url,
    )


@pytest.mark.parametrize("encoding,url,output", SAFE_URL_ENCODING_CASES)
def test_safe_url_encoding(encoding, url, output):
    _test_safe_url(url, encoding=encoding, output=output)


@pytest.mark.parametrize("url,output", SAFE_URL_URL_CASES)
def test_safe_url_url(url, output):
    _test_safe_url(url, output=output)


def _test_safe_url_string(url, *, encoding=UNSET, output):
    return _test_safe_url_func(
        url,
        encoding=encoding,
        output=output,
        func=safe_url_string,
    )


KNOWN_SAFE_URL_STRING_ENCODING_ISSUES = {
    (UNSET, ""),  # Invalid URL
    # UTF-8 encoding is not enforced in non-special URLs, or in URLs with the
    # ws or wss schemas.
    ("iso-8859-1", "a://example.com?\xa9"),
    ("iso-8859-1", "ws://example.com?\xa9"),
    ("iso-8859-1", "wss://example.com?\xa9"),
    # UTF-8 encoding is not enforced on the fragment.
    ("iso-8859-1", "https://example.com#\xa9"),
}


@pytest.mark.parametrize(
    "encoding,url,output",
    tuple(
        case
        if case[:2] not in KNOWN_SAFE_URL_STRING_ENCODING_ISSUES
        else pytest.param(*case, marks=pytest.mark.xfail(strict=True))
        for case in SAFE_URL_ENCODING_CASES
    ),
)
def test_safe_url_string_encoding(encoding, url, output):
    _test_safe_url_string(url, encoding=encoding, output=output)


KNOWN_SAFE_URL_STRING_URL_ISSUES = {
    "",  # Invalid URL
    *(case[0] for case in SAFE_URL_URL_STRIP_CASES),
    *(case[0] for case in SAFE_URL_URL_INVALID_SCHEME_CASES),
    # %3A gets decoded, going from a "a:" username to a "a" username with an
    # empty password.
    "https://a%3A@example.com",
    # Userinfo characters that the URL living standard requires escaping (:;=)
    # are not escaped.
    f"https://{USERNAME_TO_ENCODE}:{PASSWORD_TO_ENCODE}@example.com",
    "https://@\\example.com",  # Invalid URL
    "https://\x80.example",  # Invalid domain name (non-visible character)
    "https://%80.example",  # Invalid domain name (non-visible character)
    "http://192.168.0.256",  # Invalid IP address
    "http://192.168.0.0.0",  # Invalid IP address / domain name
    "http://[2a01:5cc0:1:2::4]",  # https://github.com/scrapy/w3lib/issues/193
    "http://[2a01:5cc0:1:2:3:4]",  # Invalid IPv6
    "https://example.com:",  # Removes the :
    # Does not convert \ to /
    "https://example.com\\a",
    "https://example.com\\a\\b",
    # Encodes \ and / after the first one in the path
    "https://example.com/a/b",
    "https://example.com/a\\b",
    # Some path characters that RFC 2396 and RFC 3986 require escaping (%[]|)
    # are not escaped.
    f"https://example.com/{PATH_TO_ENCODE}",
    # ? is removed
    "https://example.com?",
    "https://example.com/?",
    # Some query characters that RFC 2396 and RFC 3986 require escaping (%[]|)
    # are not escaped.
    f"a://example.com?{QUERY_TO_ENCODE}",
    # Some special query characters that RFC 2396 and RFC 3986 require escaping
    # (%[]|) or that the URL living standard requires escaping (') are not
    # escaped.
    *(
        f"{scheme}://example.com?{SPECIAL_QUERY_TO_ENCODE}"
        for scheme in _SPECIAL_SCHEMES
    ),
    # ? and # are removed
    "https://example.com#",
    "https://example.com/#",
    "https://example.com?#",
    "https://example.com/?#",
    # Some fragment characters that RFC 2396 and RFC 3986 require escaping
    # (#%[]|) are not escaped.
    f"a://example.com#{FRAGMENT_TO_ENCODE}",
}


@pytest.mark.parametrize(
    "url,output",
    tuple(
        case
        if case[0] not in KNOWN_SAFE_URL_STRING_URL_ISSUES
        else pytest.param(*case, marks=pytest.mark.xfail(strict=True))
        for case in SAFE_URL_URL_CASES
    ),
)
def test_safe_url_string_url(url, output):
    _test_safe_url_string(url, output=output)


@pytest.mark.parametrize(
    "url",
    tuple(
        case[0]
        for case in SAFE_URL_URL_CASES
        if (
            case[0] not in KNOWN_SAFE_URL_STRING_URL_ISSUES and isinstance(case[1], str)
        )
    ),
)
def test_safe_url_performance(url):
    # As you increase number, safe_url_string starts gaining by far,
    # presummably due to caching by urllib.
    number = 1  # TODO: Increase? How much?
    # Make sure the new implementation is at most this number of times as slow.
    multiplier = 200  # TODO: Lower as close to 1 as possible.

    time1 = timeit(
        f"safe_url({url!r})", "from w3lib.url import safe_url", number=number
    )
    time2 = timeit(
        f"safe_url_string({url!r})",
        "from w3lib.url import safe_url_string",
        number=number,
    )

    assert time1 <= time2 * multiplier


# If this is ever fixed upstream, decide what to do with our workaround. We
# currently provide a tee Python implementation for PyPy, which we should
# probably stop doing on PyPy versions where the bug is no longer present, but
# we still may want the implementation on other PyPy versions.
@pytest.mark.xfail(
    python_implementation() == "PyPy",
    reason="https://foss.heptapod.net/pypy/pypy/-/issues/3852",
    strict=True,
)
def test_tee():
    iterator1, _ = tee(deque([b""]))
    assert isinstance(iterator1, Iterator)


class UrlTests(unittest.TestCase):
    def test_safe_url_string_path_encoding(self):
        safeurl = safe_url_string("http://www.example.com/£", path_encoding="latin-1")
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%A3")

        safeurl = safe_url_string(
            "http://www.example.com/£?unit=µ", path_encoding="latin-1"
        )
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%A3?unit=%C2%B5")

        safeurl = safe_url_string(
            "http://www.example.com/£?unit=µ",
            encoding="latin-1",
            path_encoding="latin-1",
        )
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%A3?unit=%B5")

    def test_safe_url_string_quote_path_false(self):
        safeurl = safe_url_string('http://google.com/"hello"', quote_path=False)
        self.assertEqual(safeurl, 'http://google.com/"hello"')

    def test_safe_url_string_bytes_input(self):
        safeurl = safe_url_string(b"http://www.example.com/")
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/")

        # bytes input is assumed to be UTF-8
        safeurl = safe_url_string(b"http://www.example.com/\xc2\xb5")
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%C2%B5")

        # page-encoding encoded bytes still end up as UTF-8 sequences in path
        safeurl = safe_url_string(b"http://www.example.com/\xb5", encoding="latin1")
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%C2%B5")

        safeurl = safe_url_string(
            b"http://www.example.com/\xa3?unit=\xb5", encoding="latin1"
        )
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%C2%A3?unit=%B5")

    def test_safe_url_string_bytes_input_nonutf8(self):
        # latin1
        safeurl = safe_url_string(b"http://www.example.com/\xa3?unit=\xb5")
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%A3?unit=%B5")

        # cp1251
        # >>> 'Россия'.encode('cp1251')
        # '\xd0\xee\xf1\xf1\xe8\xff'
        safeurl = safe_url_string(
            b"http://www.example.com/country/\xd0\xee\xf1\xf1\xe8\xff"
        )
        self.assertTrue(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/country/%D0%EE%F1%F1%E8%FF")

    def test_safe_download_url(self):
        self.assertEqual(
            safe_download_url("http://www.example.org"), "http://www.example.org/"
        )
        self.assertEqual(
            safe_download_url("http://www.example.org/../"), "http://www.example.org/"
        )
        self.assertEqual(
            safe_download_url("http://www.example.org/../../images/../image"),
            "http://www.example.org/image",
        )
        self.assertEqual(
            safe_download_url("http://www.example.org/dir/"),
            "http://www.example.org/dir/",
        )
        self.assertEqual(
            safe_download_url(b"http://www.example.org/dir/"),
            "http://www.example.org/dir/",
        )

        # Encoding related tests
        self.assertEqual(
            safe_download_url(
                b"http://www.example.org?\xa3",
                encoding="latin-1",
                path_encoding="latin-1",
            ),
            "http://www.example.org/?%A3",
        )
        self.assertEqual(
            safe_download_url(
                b"http://www.example.org?\xc2\xa3",
                encoding="utf-8",
                path_encoding="utf-8",
            ),
            "http://www.example.org/?%C2%A3",
        )
        self.assertEqual(
            safe_download_url(
                b"http://www.example.org/\xc2\xa3?\xc2\xa3",
                encoding="utf-8",
                path_encoding="latin-1",
            ),
            "http://www.example.org/%A3?%C2%A3",
        )

    def test_is_url(self):
        self.assertTrue(is_url("http://www.example.org"))
        self.assertTrue(is_url("https://www.example.org"))
        self.assertTrue(is_url("file:///some/path"))
        self.assertFalse(is_url("foo://bar"))
        self.assertFalse(is_url("foo--bar"))

    def test_url_query_parameter(self):
        self.assertEqual(
            url_query_parameter("product.html?id=200&foo=bar", "id"), "200"
        )
        self.assertEqual(
            url_query_parameter("product.html?id=200&foo=bar", "notthere", "mydefault"),
            "mydefault",
        )
        self.assertEqual(url_query_parameter("product.html?id=", "id"), None)
        self.assertEqual(
            url_query_parameter("product.html?id=", "id", keep_blank_values=1), ""
        )

    def test_url_query_parameter_2(self):
        """
        This problem was seen several times in the feeds. Sometime affiliate URLs contains
        nested encoded affiliate URL with direct URL as parameters. For example:
        aff_url1 = 'http://www.tkqlhce.com/click-2590032-10294381?url=http%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FArgosCreateReferral%3FstoreId%3D10001%26langId%3D-1%26referrer%3DCOJUN%26params%3Dadref%253DGarden+and+DIY-%3EGarden+furniture-%3EChildren%26%2339%3Bs+garden+furniture%26referredURL%3Dhttp%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FProductDisplay%253FstoreId%253D10001%2526catalogId%253D1500001501%2526productId%253D1500357023%2526langId%253D-1'
        the typical code to extract needed URL from it is:
        aff_url2 = url_query_parameter(aff_url1, 'url')
        after this aff2_url is:
        'http://www.argos.co.uk/webapp/wcs/stores/servlet/ArgosCreateReferral?storeId=10001&langId=-1&referrer=COJUN&params=adref%3DGarden and DIY->Garden furniture->Children&#39;s gardenfurniture&referredURL=http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay%3FstoreId%3D10001%26catalogId%3D1500001501%26productId%3D1500357023%26langId%3D-1'
        the direct URL extraction is
        url = url_query_parameter(aff_url2, 'referredURL')
        but this will not work, because aff_url2 contains &#39; (comma sign encoded in the feed)
        and the URL extraction will fail, current workaround was made in the spider,
        just a replace for &#39; to %27
        """
        return  # FIXME: this test should pass but currently doesnt
        # correct case
        aff_url1 = "http://www.anrdoezrs.net/click-2590032-10294381?url=http%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FArgosCreateReferral%3FstoreId%3D10001%26langId%3D-1%26referrer%3DCOJUN%26params%3Dadref%253DGarden+and+DIY-%3EGarden+furniture-%3EGarden+table+and+chair+sets%26referredURL%3Dhttp%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FProductDisplay%253FstoreId%253D10001%2526catalogId%253D1500001501%2526productId%253D1500357199%2526langId%253D-1"
        aff_url2 = url_query_parameter(aff_url1, "url")
        self.assertEqual(
            aff_url2,
            "http://www.argos.co.uk/webapp/wcs/stores/servlet/ArgosCreateReferral?storeId=10001&langId=-1&referrer=COJUN&params=adref%3DGarden and DIY->Garden furniture->Garden table and chair sets&referredURL=http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay%3FstoreId%3D10001%26catalogId%3D1500001501%26productId%3D1500357199%26langId%3D-1",
        )
        prod_url = url_query_parameter(aff_url2, "referredURL")
        self.assertEqual(
            prod_url,
            "http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay?storeId=10001&catalogId=1500001501&productId=1500357199&langId=-1",
        )
        # weird case
        aff_url1 = "http://www.tkqlhce.com/click-2590032-10294381?url=http%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FArgosCreateReferral%3FstoreId%3D10001%26langId%3D-1%26referrer%3DCOJUN%26params%3Dadref%253DGarden+and+DIY-%3EGarden+furniture-%3EChildren%26%2339%3Bs+garden+furniture%26referredURL%3Dhttp%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FProductDisplay%253FstoreId%253D10001%2526catalogId%253D1500001501%2526productId%253D1500357023%2526langId%253D-1"
        aff_url2 = url_query_parameter(aff_url1, "url")
        self.assertEqual(
            aff_url2,
            "http://www.argos.co.uk/webapp/wcs/stores/servlet/ArgosCreateReferral?storeId=10001&langId=-1&referrer=COJUN&params=adref%3DGarden and DIY->Garden furniture->Children&#39;s garden furniture&referredURL=http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay%3FstoreId%3D10001%26catalogId%3D1500001501%26productId%3D1500357023%26langId%3D-1",
        )
        prod_url = url_query_parameter(aff_url2, "referredURL")
        # fails, prod_url is None now
        self.assertEqual(
            prod_url,
            "http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay?storeId=10001&catalogId=1500001501&productId=1500357023&langId=-1",
        )

    def test_add_or_replace_parameter(self):
        url = "http://domain/test"
        self.assertEqual(
            add_or_replace_parameter(url, "arg", "v"), "http://domain/test?arg=v"
        )
        url = "http://domain/test?arg1=v1&arg2=v2&arg3=v3"
        self.assertEqual(
            add_or_replace_parameter(url, "arg4", "v4"),
            "http://domain/test?arg1=v1&arg2=v2&arg3=v3&arg4=v4",
        )
        self.assertEqual(
            add_or_replace_parameter(url, "arg3", "nv3"),
            "http://domain/test?arg1=v1&arg2=v2&arg3=nv3",
        )

        self.assertEqual(
            add_or_replace_parameter(
                "http://domain/moreInfo.asp?prodID=", "prodID", "20"
            ),
            "http://domain/moreInfo.asp?prodID=20",
        )
        url = "http://rmc-offers.co.uk/productlist.asp?BCat=2%2C60&CatID=60"
        self.assertEqual(
            add_or_replace_parameter(url, "BCat", "newvalue"),
            "http://rmc-offers.co.uk/productlist.asp?BCat=newvalue&CatID=60",
        )
        url = "http://rmc-offers.co.uk/productlist.asp?BCat=2,60&CatID=60"
        self.assertEqual(
            add_or_replace_parameter(url, "BCat", "newvalue"),
            "http://rmc-offers.co.uk/productlist.asp?BCat=newvalue&CatID=60",
        )
        url = "http://rmc-offers.co.uk/productlist.asp?"
        self.assertEqual(
            add_or_replace_parameter(url, "BCat", "newvalue"),
            "http://rmc-offers.co.uk/productlist.asp?BCat=newvalue",
        )

        url = "http://example.com/?version=1&pageurl=http%3A%2F%2Fwww.example.com%2Ftest%2F%23fragment%3Dy&param2=value2"
        self.assertEqual(
            add_or_replace_parameter(url, "version", "2"),
            "http://example.com/?version=2&pageurl=http%3A%2F%2Fwww.example.com%2Ftest%2F%23fragment%3Dy&param2=value2",
        )
        self.assertEqual(
            add_or_replace_parameter(url, "pageurl", "test"),
            "http://example.com/?version=1&pageurl=test&param2=value2",
        )

        url = "http://domain/test?arg1=v1&arg2=v2&arg1=v3"
        self.assertEqual(
            add_or_replace_parameter(url, "arg4", "v4"),
            "http://domain/test?arg1=v1&arg2=v2&arg1=v3&arg4=v4",
        )
        self.assertEqual(
            add_or_replace_parameter(url, "arg1", "v3"),
            "http://domain/test?arg1=v3&arg2=v2",
        )

    @pytest.mark.xfail(reason="https://github.com/scrapy/w3lib/issues/164")
    def test_add_or_replace_parameter_fail(self):
        self.assertEqual(
            add_or_replace_parameter(
                "http://domain/test?arg1=v1;arg2=v2", "arg1", "v3"
            ),
            "http://domain/test?arg1=v3&arg2=v2",
        )

    def test_add_or_replace_parameters(self):
        url = "http://domain/test"
        self.assertEqual(
            add_or_replace_parameters(url, {"arg": "v"}), "http://domain/test?arg=v"
        )
        url = "http://domain/test?arg1=v1&arg2=v2&arg3=v3"
        self.assertEqual(
            add_or_replace_parameters(url, {"arg4": "v4"}),
            "http://domain/test?arg1=v1&arg2=v2&arg3=v3&arg4=v4",
        )
        self.assertEqual(
            add_or_replace_parameters(url, {"arg4": "v4", "arg3": "v3new"}),
            "http://domain/test?arg1=v1&arg2=v2&arg3=v3new&arg4=v4",
        )
        url = "http://domain/test?arg1=v1&arg2=v2&arg1=v3"
        self.assertEqual(
            add_or_replace_parameters(url, {"arg4": "v4"}),
            "http://domain/test?arg1=v1&arg2=v2&arg1=v3&arg4=v4",
        )
        self.assertEqual(
            add_or_replace_parameters(url, {"arg1": "v3"}),
            "http://domain/test?arg1=v3&arg2=v2",
        )

    def test_add_or_replace_parameters_does_not_change_input_param(self):
        url = "http://domain/test?arg=original"
        input_param = {"arg": "value"}
        add_or_replace_parameters(url, input_param)  # noqa
        self.assertEqual(input_param, {"arg": "value"})

    def test_url_query_cleaner(self):
        self.assertEqual("product.html", url_query_cleaner("product.html?"))
        self.assertEqual("product.html", url_query_cleaner("product.html?&"))
        self.assertEqual(
            "product.html?id=200",
            url_query_cleaner("product.html?id=200&foo=bar&name=wired", ["id"]),
        )
        self.assertEqual(
            "product.html?id=200",
            url_query_cleaner("product.html?&id=200&&foo=bar&name=wired", ["id"]),
        )
        self.assertEqual(
            "product.html", url_query_cleaner("product.html?foo=bar&name=wired", ["id"])
        )
        self.assertEqual(
            "product.html?id=200&name=wired",
            url_query_cleaner("product.html?id=200&foo=bar&name=wired", ["id", "name"]),
        )
        self.assertEqual(
            "product.html?id",
            url_query_cleaner("product.html?id&other=3&novalue=", ["id"]),
        )
        # default is to remove duplicate keys
        self.assertEqual(
            "product.html?d=1",
            url_query_cleaner("product.html?d=1&e=b&d=2&d=3&other=other", ["d"]),
        )
        # unique=False disables duplicate keys filtering
        self.assertEqual(
            "product.html?d=1&d=2&d=3",
            url_query_cleaner(
                "product.html?d=1&e=b&d=2&d=3&other=other", ["d"], unique=False
            ),
        )
        self.assertEqual(
            "product.html?id=200&foo=bar",
            url_query_cleaner(
                "product.html?id=200&foo=bar&name=wired#id20", ["id", "foo"]
            ),
        )
        self.assertEqual(
            "product.html?foo=bar&name=wired",
            url_query_cleaner(
                "product.html?id=200&foo=bar&name=wired", ["id"], remove=True
            ),
        )
        self.assertEqual(
            "product.html?name=wired",
            url_query_cleaner(
                "product.html?id=2&foo=bar&name=wired", ["id", "foo"], remove=True
            ),
        )
        self.assertEqual(
            "product.html?foo=bar&name=wired",
            url_query_cleaner(
                "product.html?id=2&foo=bar&name=wired", ["id", "footo"], remove=True
            ),
        )
        self.assertEqual(
            "product.html", url_query_cleaner("product.html", ["id"], remove=True)
        )
        self.assertEqual(
            "product.html", url_query_cleaner("product.html?&", ["id"], remove=True)
        )
        self.assertEqual(
            "product.html?foo=bar",
            url_query_cleaner("product.html?foo=bar&name=wired", "foo"),
        )
        self.assertEqual(
            "product.html?foobar=wired",
            url_query_cleaner("product.html?foo=bar&foobar=wired", "foobar"),
        )

    def test_url_query_cleaner_keep_fragments(self):
        self.assertEqual(
            "product.html?id=200#foo",
            url_query_cleaner(
                "product.html?id=200&foo=bar&name=wired#foo",
                ["id"],
                keep_fragments=True,
            ),
        )
        self.assertEqual(
            "product.html?id=200",
            url_query_cleaner(
                "product.html?id=200&foo=bar&name=wired", ["id"], keep_fragments=True
            ),
        )

    def test_path_to_file_uri(self):
        if os.name == "nt":
            self.assertEqual(
                path_to_file_uri(r"C:\\windows\clock.avi"),
                "file:///C:/windows/clock.avi",
            )
        else:
            self.assertEqual(
                path_to_file_uri("/some/path.txt"), "file:///some/path.txt"
            )

        fn = "test.txt"
        x = path_to_file_uri(fn)
        self.assertTrue(x.startswith("file:///"))
        self.assertEqual(file_uri_to_path(x).lower(), os.path.abspath(fn).lower())

    def test_file_uri_to_path(self):
        if os.name == "nt":
            self.assertEqual(
                file_uri_to_path("file:///C:/windows/clock.avi"),
                r"C:\\windows\clock.avi",
            )
            uri = "file:///C:/windows/clock.avi"
            uri2 = path_to_file_uri(file_uri_to_path(uri))
            self.assertEqual(uri, uri2)
        else:
            self.assertEqual(
                file_uri_to_path("file:///path/to/test.txt"), "/path/to/test.txt"
            )
            self.assertEqual(file_uri_to_path("/path/to/test.txt"), "/path/to/test.txt")
            uri = "file:///path/to/test.txt"
            uri2 = path_to_file_uri(file_uri_to_path(uri))
            self.assertEqual(uri, uri2)

        self.assertEqual(file_uri_to_path("test.txt"), "test.txt")

    def test_any_to_uri(self):
        if os.name == "nt":
            self.assertEqual(
                any_to_uri(r"C:\\windows\clock.avi"), "file:///C:/windows/clock.avi"
            )
        else:
            self.assertEqual(any_to_uri("/some/path.txt"), "file:///some/path.txt")
        self.assertEqual(any_to_uri("file:///some/path.txt"), "file:///some/path.txt")
        self.assertEqual(
            any_to_uri("http://www.example.com/some/path.txt"),
            "http://www.example.com/some/path.txt",
        )


class CanonicalizeUrlTest(unittest.TestCase):
    def test_canonicalize_url(self):
        # simplest case
        self.assertEqual(
            canonicalize_url("http://www.example.com/"), "http://www.example.com/"
        )

    def test_return_str(self):
        assert isinstance(canonicalize_url("http://www.example.com"), str)
        assert isinstance(canonicalize_url(b"http://www.example.com"), str)

    def test_append_missing_path(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com"), "http://www.example.com/"
        )

    def test_typical_usage(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?a=1&b=2&c=3"),
            "http://www.example.com/do?a=1&b=2&c=3",
        )
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?c=1&b=2&a=3"),
            "http://www.example.com/do?a=3&b=2&c=1",
        )
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?&a=1"),
            "http://www.example.com/do?a=1",
        )

    def test_port_number(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com:8888/do?a=1&b=2&c=3"),
            "http://www.example.com:8888/do?a=1&b=2&c=3",
        )
        # trailing empty ports are removed
        self.assertEqual(
            canonicalize_url("http://www.example.com:/do?a=1&b=2&c=3"),
            "http://www.example.com/do?a=1&b=2&c=3",
        )

    def test_sorting(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?c=3&b=5&b=2&a=50"),
            "http://www.example.com/do?a=50&b=2&b=5&c=3",
        )

    def test_keep_blank_values(self):
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/do?b=&a=2", keep_blank_values=False
            ),
            "http://www.example.com/do?a=2",
        )
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?b=&a=2"),
            "http://www.example.com/do?a=2&b=",
        )
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/do?b=&c&a=2", keep_blank_values=False
            ),
            "http://www.example.com/do?a=2",
        )
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?b=&c&a=2"),
            "http://www.example.com/do?a=2&b=&c=",
        )

        self.assertEqual(
            canonicalize_url("http://www.example.com/do?1750,4"),
            "http://www.example.com/do?1750%2C4=",
        )

    def test_spaces(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?q=a space&a=1"),
            "http://www.example.com/do?a=1&q=a+space",
        )
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?q=a+space&a=1"),
            "http://www.example.com/do?a=1&q=a+space",
        )
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?q=a%20space&a=1"),
            "http://www.example.com/do?a=1&q=a+space",
        )

    def test_canonicalize_url_unicode_path(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/résumé"),
            "http://www.example.com/r%C3%A9sum%C3%A9",
        )

    def test_canonicalize_url_unicode_query_string(self):
        # default encoding for path and query is UTF-8
        self.assertEqual(
            canonicalize_url("http://www.example.com/résumé?q=résumé"),
            "http://www.example.com/r%C3%A9sum%C3%A9?q=r%C3%A9sum%C3%A9",
        )

        # passed encoding will affect query string
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/résumé?q=résumé", encoding="latin1"
            ),
            "http://www.example.com/r%C3%A9sum%C3%A9?q=r%E9sum%E9",
        )

        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/résumé?country=Россия", encoding="cp1251"
            ),
            "http://www.example.com/r%C3%A9sum%C3%A9?country=%D0%EE%F1%F1%E8%FF",
        )

    def test_canonicalize_url_unicode_query_string_wrong_encoding(self):
        # trying to encode with wrong encoding
        # fallback to UTF-8
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/résumé?currency=€", encoding="latin1"
            ),
            "http://www.example.com/r%C3%A9sum%C3%A9?currency=%E2%82%AC",
        )

        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/résumé?country=Россия", encoding="latin1"
            ),
            "http://www.example.com/r%C3%A9sum%C3%A9?country=%D0%A0%D0%BE%D1%81%D1%81%D0%B8%D1%8F",
        )

    def test_normalize_percent_encoding_in_paths(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/r%c3%a9sum%c3%a9"),
            "http://www.example.com/r%C3%A9sum%C3%A9",
        )

        # non-UTF8 encoded sequences: they should be kept untouched, only upper-cased
        # 'latin1'-encoded sequence in path
        self.assertEqual(
            canonicalize_url("http://www.example.com/a%a3do"),
            "http://www.example.com/a%A3do",
        )

        # 'latin1'-encoded path, UTF-8 encoded query string
        self.assertEqual(
            canonicalize_url("http://www.example.com/a%a3do?q=r%c3%a9sum%c3%a9"),
            "http://www.example.com/a%A3do?q=r%C3%A9sum%C3%A9",
        )

        # 'latin1'-encoded path and query string
        self.assertEqual(
            canonicalize_url("http://www.example.com/a%a3do?q=r%e9sum%e9"),
            "http://www.example.com/a%A3do?q=r%E9sum%E9",
        )

        url = "https://example.com/a%23b%2cc#bash"
        canonical = canonicalize_url(url)
        # %23 is not accidentally interpreted as a URL fragment separator
        self.assertEqual(canonical, "https://example.com/a%23b,c")
        self.assertEqual(canonical, canonicalize_url(canonical))

    def test_normalize_percent_encoding_in_query_arguments(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?k=b%a3"),
            "http://www.example.com/do?k=b%A3",
        )

        self.assertEqual(
            canonicalize_url("http://www.example.com/do?k=r%c3%a9sum%c3%a9"),
            "http://www.example.com/do?k=r%C3%A9sum%C3%A9",
        )

    def test_non_ascii_percent_encoding_in_paths(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/a do?a=1"),
            "http://www.example.com/a%20do?a=1",
        )

        self.assertEqual(
            canonicalize_url("http://www.example.com/a %20do?a=1"),
            "http://www.example.com/a%20%20do?a=1",
        )

        self.assertEqual(
            canonicalize_url("http://www.example.com/a do£.html?a=1"),
            "http://www.example.com/a%20do%C2%A3.html?a=1",
        )

        self.assertEqual(
            canonicalize_url(b"http://www.example.com/a do\xc2\xa3.html?a=1"),
            "http://www.example.com/a%20do%C2%A3.html?a=1",
        )

    def test_non_ascii_percent_encoding_in_query_arguments(self):
        self.assertEqual(
            canonicalize_url("http://www.example.com/do?price=£500&a=5&z=3"),
            "http://www.example.com/do?a=5&price=%C2%A3500&z=3",
        )
        self.assertEqual(
            canonicalize_url(b"http://www.example.com/do?price=\xc2\xa3500&a=5&z=3"),
            "http://www.example.com/do?a=5&price=%C2%A3500&z=3",
        )
        self.assertEqual(
            canonicalize_url(b"http://www.example.com/do?price(\xc2\xa3)=500&a=1"),
            "http://www.example.com/do?a=1&price%28%C2%A3%29=500",
        )

    def test_urls_with_auth_and_ports(self):
        self.assertEqual(
            canonicalize_url("http://user:pass@www.example.com:81/do?now=1"),
            "http://user:pass@www.example.com:81/do?now=1",
        )

    def test_remove_fragments(self):
        self.assertEqual(
            canonicalize_url("http://user:pass@www.example.com/do?a=1#frag"),
            "http://user:pass@www.example.com/do?a=1",
        )
        self.assertEqual(
            canonicalize_url(
                "http://user:pass@www.example.com/do?a=1#frag", keep_fragments=True
            ),
            "http://user:pass@www.example.com/do?a=1#frag",
        )

    def test_dont_convert_safe_characters(self):
        # dont convert safe characters to percent encoding representation
        self.assertEqual(
            canonicalize_url(
                "http://www.simplybedrooms.com/White-Bedroom-Furniture/Bedroom-Mirror:-Josephine-Cheval-Mirror.html"
            ),
            "http://www.simplybedrooms.com/White-Bedroom-Furniture/Bedroom-Mirror:-Josephine-Cheval-Mirror.html",
        )

    def test_safe_characters_unicode(self):
        # urllib.quote uses a mapping cache of encoded characters. when parsing
        # an already percent-encoded url, it will fail if that url was not
        # percent-encoded as utf-8, that's why canonicalize_url must always
        # convert the urls to string. the following test asserts that
        # functionality.
        self.assertEqual(
            canonicalize_url("http://www.example.com/caf%E9-con-leche.htm"),
            "http://www.example.com/caf%E9-con-leche.htm",
        )

    def test_domains_are_case_insensitive(self):
        self.assertEqual(
            canonicalize_url("http://www.EXAMPLE.com/"), "http://www.example.com/"
        )

    def test_canonicalize_idns(self):
        self.assertEqual(
            canonicalize_url("http://www.bücher.de?q=bücher"),
            "http://www.xn--bcher-kva.de/?q=b%C3%BCcher",
        )
        # Japanese (+ reordering query parameters)
        self.assertEqual(
            canonicalize_url("http://はじめよう.みんな/?query=サ&maxResults=5"),
            "http://xn--p8j9a0d9c9a.xn--q9jyb4c/?maxResults=5&query=%E3%82%B5",
        )

    def test_quoted_slash_and_question_sign(self):
        self.assertEqual(
            canonicalize_url("http://foo.com/AC%2FDC+rocks%3f/?yeah=1"),
            "http://foo.com/AC%2FDC+rocks%3F/?yeah=1",
        )
        self.assertEqual(
            canonicalize_url("http://foo.com/AC%2FDC/"), "http://foo.com/AC%2FDC/"
        )

    def test_canonicalize_urlparsed(self):
        # canonicalize_url() can be passed an already urlparse'd URL
        self.assertEqual(
            canonicalize_url(urlparse("http://www.example.com/résumé?q=résumé")),
            "http://www.example.com/r%C3%A9sum%C3%A9?q=r%C3%A9sum%C3%A9",
        )
        self.assertEqual(
            canonicalize_url(urlparse("http://www.example.com/caf%e9-con-leche.htm")),
            "http://www.example.com/caf%E9-con-leche.htm",
        )
        self.assertEqual(
            canonicalize_url(
                urlparse("http://www.example.com/a%a3do?q=r%c3%a9sum%c3%a9")
            ),
            "http://www.example.com/a%A3do?q=r%C3%A9sum%C3%A9",
        )

    def test_canonicalize_parse_url(self):
        # parse_url() wraps urlparse and is used in link extractors
        self.assertEqual(
            canonicalize_url(parse_url("http://www.example.com/résumé?q=résumé")),
            "http://www.example.com/r%C3%A9sum%C3%A9?q=r%C3%A9sum%C3%A9",
        )
        self.assertEqual(
            canonicalize_url(parse_url("http://www.example.com/caf%e9-con-leche.htm")),
            "http://www.example.com/caf%E9-con-leche.htm",
        )
        self.assertEqual(
            canonicalize_url(
                parse_url("http://www.example.com/a%a3do?q=r%c3%a9sum%c3%a9")
            ),
            "http://www.example.com/a%A3do?q=r%C3%A9sum%C3%A9",
        )

    def test_canonicalize_url_idempotence(self):
        for url, enc in [
            ("http://www.bücher.de/résumé?q=résumé", "utf8"),
            ("http://www.example.com/résumé?q=résumé", "latin1"),
            ("http://www.example.com/résumé?country=Россия", "cp1251"),
            ("http://はじめよう.みんな/?query=サ&maxResults=5", "iso2022jp"),
        ]:
            canonicalized = canonicalize_url(url, encoding=enc)

            # if we canonicalize again, we ge the same result
            self.assertEqual(
                canonicalize_url(canonicalized, encoding=enc), canonicalized
            )

            # without encoding, already canonicalized URL is canonicalized identically
            self.assertEqual(canonicalize_url(canonicalized), canonicalized)

    def test_canonicalize_url_idna_exceptions(self):
        # missing DNS label
        self.assertEqual(
            canonicalize_url("http://.example.com/résumé?q=résumé"),
            "http://.example.com/r%C3%A9sum%C3%A9?q=r%C3%A9sum%C3%A9",
        )

        # DNS label too long
        self.assertEqual(
            canonicalize_url(f"http://www.{'example' * 11}.com/résumé?q=résumé"),
            f"http://www.{'example' * 11}.com/r%C3%A9sum%C3%A9?q=r%C3%A9sum%C3%A9",
        )

    def test_preserve_nonfragment_hash(self):
        # don't decode `%23` to `#`
        self.assertEqual(
            canonicalize_url("http://www.example.com/path/to/%23/foo/bar"),
            "http://www.example.com/path/to/%23/foo/bar",
        )
        self.assertEqual(
            canonicalize_url("http://www.example.com/path/to/%23/foo/bar#frag"),
            "http://www.example.com/path/to/%23/foo/bar",
        )
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/path/to/%23/foo/bar#frag", keep_fragments=True
            ),
            "http://www.example.com/path/to/%23/foo/bar#frag",
        )
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/path/to/%23/foo/bar?url=http%3A%2F%2Fwww.example.com%2Fpath%2Fto%2F%23%2Fbar%2Ffoo"
            ),
            "http://www.example.com/path/to/%23/foo/bar?url=http%3A%2F%2Fwww.example.com%2Fpath%2Fto%2F%23%2Fbar%2Ffoo",
        )
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/path/to/%23/foo/bar?url=http%3A%2F%2Fwww.example.com%2F%2Fpath%2Fto%2F%23%2Fbar%2Ffoo#frag"
            ),
            "http://www.example.com/path/to/%23/foo/bar?url=http%3A%2F%2Fwww.example.com%2F%2Fpath%2Fto%2F%23%2Fbar%2Ffoo",
        )
        self.assertEqual(
            canonicalize_url(
                "http://www.example.com/path/to/%23/foo/bar?url=http%3A%2F%2Fwww.example.com%2F%2Fpath%2Fto%2F%23%2Fbar%2Ffoo#frag",
                keep_fragments=True,
            ),
            "http://www.example.com/path/to/%23/foo/bar?url=http%3A%2F%2Fwww.example.com%2F%2Fpath%2Fto%2F%23%2Fbar%2Ffoo#frag",
        )

    def test_strip_spaces(self):
        self.assertEqual(
            canonicalize_url(" https://example.com"), "https://example.com/"
        )
        self.assertEqual(
            canonicalize_url("https://example.com "), "https://example.com/"
        )
        self.assertEqual(
            canonicalize_url(" https://example.com "), "https://example.com/"
        )


class DataURITests(unittest.TestCase):
    def test_default_mediatype_charset(self):
        result = parse_data_uri("data:,A%20brief%20note")
        self.assertEqual(result.media_type, "text/plain")
        self.assertEqual(result.media_type_parameters, {"charset": "US-ASCII"})
        self.assertEqual(result.data, b"A brief note")

    def test_text_uri(self):
        result = parse_data_uri("data:,A%20brief%20note")
        self.assertEqual(result.data, b"A brief note")

    def test_bytes_uri(self):
        result = parse_data_uri(b"data:,A%20brief%20note")
        self.assertEqual(result.data, b"A brief note")

    def test_unicode_uri(self):
        result = parse_data_uri("data:,é")
        self.assertEqual(result.data, "é".encode())

    def test_default_mediatype(self):
        result = parse_data_uri("data:;charset=iso-8859-7,%be%d3%be")
        self.assertEqual(result.media_type, "text/plain")
        self.assertEqual(result.media_type_parameters, {"charset": "iso-8859-7"})
        self.assertEqual(result.data, b"\xbe\xd3\xbe")

    def test_text_charset(self):
        result = parse_data_uri("data:text/plain;charset=iso-8859-7,%be%d3%be")
        self.assertEqual(result.media_type, "text/plain")
        self.assertEqual(result.media_type_parameters, {"charset": "iso-8859-7"})
        self.assertEqual(result.data, b"\xbe\xd3\xbe")

    def test_mediatype_parameters(self):
        result = parse_data_uri(
            "data:text/plain;"
            "foo=%22foo;bar%5C%22%22;"
            "charset=utf-8;"
            "bar=%22foo;%5C%22foo%20;/%20,%22,"
            "%CE%8E%CE%A3%CE%8E"
        )

        self.assertEqual(result.media_type, "text/plain")
        self.assertEqual(
            result.media_type_parameters,
            {"charset": "utf-8", "foo": 'foo;bar"', "bar": 'foo;"foo ;/ ,'},
        )
        self.assertEqual(result.data, b"\xce\x8e\xce\xa3\xce\x8e")

    def test_base64(self):
        result = parse_data_uri("data:text/plain;base64," "SGVsbG8sIHdvcmxkLg%3D%3D")
        self.assertEqual(result.media_type, "text/plain")
        self.assertEqual(result.data, b"Hello, world.")

    def test_base64_spaces(self):
        result = parse_data_uri(
            "data:text/plain;base64,SGVsb%20G8sIH%0A%20%20"
            "dvcm%20%20%20xk%20Lg%3D%0A%3D"
        )
        self.assertEqual(result.media_type, "text/plain")
        self.assertEqual(result.data, b"Hello, world.")

        result = parse_data_uri(
            "data:text/plain;base64,SGVsb G8sIH\n  " "dvcm   xk Lg%3D\n%3D"
        )
        self.assertEqual(result.media_type, "text/plain")
        self.assertEqual(result.data, b"Hello, world.")

    def test_wrong_base64_param(self):
        with self.assertRaises(ValueError):
            parse_data_uri("data:text/plain;baes64,SGVsbG8sIHdvcmxkLg%3D%3D")

    def test_missing_comma(self):
        with self.assertRaises(ValueError):
            parse_data_uri("data:A%20brief%20note")

    def test_missing_scheme(self):
        with self.assertRaises(ValueError):
            parse_data_uri("text/plain,A%20brief%20note")

    def test_wrong_scheme(self):
        with self.assertRaises(ValueError):
            parse_data_uri("http://example.com/")

    def test_scheme_case_insensitive(self):
        result = parse_data_uri("DATA:,A%20brief%20note")
        self.assertEqual(result.data, b"A brief note")
        result = parse_data_uri("DaTa:,A%20brief%20note")
        self.assertEqual(result.data, b"A brief note")


if __name__ == "__main__":
    unittest.main()
