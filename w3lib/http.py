from base64 import urlsafe_b64encode


def headers_raw_to_dict(headers_raw, strict=False):
    r"""
    Convert raw headers (single multi-line bytestring)
    to a dictionary.

    `strict` is a bool parameter controlling the multi-line parsing behavior.
    If 'True', only the character sequence '\r\n' is considered as the line
    delimiter, as per the HTTP specification (e.g., RFC 2616). If 'False'
    (default), lines are delimited by 'str.splitlines()' and a wider range
    of character(s) are considered as line boundaries.

    For example:

    >>> import w3lib.http
    >>> w3lib.http.headers_raw_to_dict(b"Content-type: text/html\n\rAccept: gzip\n\n")   # doctest: +SKIP
    {'Content-type': ['text/html'], 'Accept': ['gzip']}

    Incorrect input:

    >>> w3lib.http.headers_raw_to_dict(b"Content-typt gzip\n\n")
    {}
    >>>

    Argument is ``None`` (return ``None``):

    >>> w3lib.http.headers_raw_to_dict(None)
    >>>

    """

    if headers_raw is None:
        return None

    if strict:
        headers = []
        for line in headers_raw.split(b'\r\n'):
            if line.startswith(b' ') or line.startswith(b'\t'):
                try:
                    headers[-1] += b'\r\n' + line
                except IndexError:
                    raise ValueError('Malformed raw headers')
            else:
                headers.append(line)
    else:
        headers = headers_raw.splitlines()

    headers_tuples = [header.split(b':', 1) for header in headers]

    result_dict = {}
    for header_item in headers_tuples:
        if not len(header_item) == 2:
            continue

        item_key = header_item[0].strip()
        item_value = header_item[1].strip()

        if item_key in result_dict:
            result_dict[item_key].append(item_value)
        else:
            result_dict[item_key] = [item_value]

    return result_dict


def headers_dict_to_raw(headers_dict):
    r"""
    Returns a raw HTTP headers representation of headers

    For example:

    >>> import w3lib.http
    >>> w3lib.http.headers_dict_to_raw({b'Content-type': b'text/html', b'Accept': b'gzip'}) # doctest: +SKIP
    'Content-type: text/html\\r\\nAccept: gzip'
    >>>

    Note that keys and values must be bytes.

    Argument is ``None`` (returns ``None``):

    >>> w3lib.http.headers_dict_to_raw(None)
    >>>

    """

    if headers_dict is None:
        return None
    raw_lines = []
    for key, value in headers_dict.items():
        if isinstance(value, bytes):
            raw_lines.append(b": ".join([key, value]))
        elif isinstance(value, (list, tuple)):
            for v in value:
                raw_lines.append(b": ".join([key, v]))
    return b'\r\n'.join(raw_lines)


def basic_auth_header(username, password, encoding='ISO-8859-1'):
    """
    Return an `Authorization` header field value for `HTTP Basic Access Authentication (RFC 2617)`_

    >>> import w3lib.http
    >>> w3lib.http.basic_auth_header('someuser', 'somepass')
    'Basic c29tZXVzZXI6c29tZXBhc3M='

    .. _HTTP Basic Access Authentication (RFC 2617): http://www.ietf.org/rfc/rfc2617.txt

    """

    auth = "%s:%s" % (username, password)
    if not isinstance(auth, bytes):
        # XXX: RFC 2617 doesn't define encoding, but ISO-8859-1
        # seems to be the most widely used encoding here. See also:
        # http://greenbytes.de/tech/webdav/draft-ietf-httpauth-basicauth-enc-latest.html
        auth = auth.encode(encoding)
    return b'Basic ' + urlsafe_b64encode(auth)
