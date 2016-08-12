import base64
import re

import six

if six.PY2:
    from urllib import unquote
else:
    from urllib.parse import unquote_to_bytes as unquote


# ASCII characters.
_char = set(map(chr, range(127)))

# RFC 2045 token.
_token = r'[{}]+'.format(re.escape(''.join(_char -
                                           # Control characters.
                                           set(map(chr, range(0, 32))) -
                                           # tspecials and space.
                                           set('()<>@,;:\\"/[]?= '))))

# RFC 822 quoted-string, without surrounding quotation marks.
_quoted_string = r'(?:[{}]|(?:\\[{}]))*'.format(
    re.escape(''.join(_char - {'"', '\\', '\r'})),
    re.escape(''.join(_char))
)

# Encode the regular expression strings to make them into bytes, as Python 3
# bytes have no format() method, but bytes must be passed to re.compile() in
# order to make a pattern object that can be used to match on bytes.

# RFC 2397 mediatype.
_mediatype_pattern = re.compile(
    r'{token}/{token}'.format(token=_token).encode()
)
_mediatype_parameter_pattern = re.compile(
    r';({token})=(?:({token})|"({quoted})")'.format(token=_token,
                                                    quoted=_quoted_string
                                                    ).encode()
)


def parse_data_uri(uri):
    """

    Parse a data: URI, returning a 3-tuple of media type, dictionary of media
    type parameters, and data.

    """

    scheme, uri = uri.split(':', 1)
    if scheme != 'data':
        raise ValueError("not a data URI")

    # RFC 3986 section 2.1 allows percent encoding to escape characters that
    # would be interpreted as delimiters, implying that actual delimiters
    # should not be percent-encoded.
    # Decoding before parsing will allow malformed URIs with percent-encoded
    # delimiters, but it makes parsing easier and should not affect
    # well-formed URIs, as the delimiters used in this URI scheme are not
    # allowed, percent-encoded or not, in tokens.
    uri = unquote(uri)

    media_type = "text/plain"
    media_type_params = {}

    m = _mediatype_pattern.match(uri)
    if m:
        media_type = m.group().decode()
        uri = uri[m.end():]
    else:
        media_type_params['charset'] = "US-ASCII"

    while True:
        m = _mediatype_parameter_pattern.match(uri)
        if m:
            attribute, value, value_quoted = m.groups()
            if value_quoted:
                value = re.sub(br'\\(.)', r'\1', value_quoted)
            media_type_params[attribute.decode()] = value.decode()
            uri = uri[m.end():]
        else:
            break

    is_base64, data = uri.split(b',', 1)
    if is_base64:
        if is_base64 != b";base64":
            raise ValueError("invalid data URI")
        data = base64.b64decode(data)

    return media_type, media_type_params, data
