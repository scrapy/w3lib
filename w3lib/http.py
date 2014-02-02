from base64 import urlsafe_b64encode

def headers_raw_to_dict(headers_raw):
    """
    Convert raw headers (single multi-line string)
    to a dictionary.

    For example:

    >>> import w3lib.http
    >>> w3lib.http.headers_raw_to_dict("Content-type: text/html\\n\\rAccept: gzip\\n\\n")   # doctest: +SKIP
    {'Content-type': ['text/html'], 'Accept': ['gzip']}

    Incorrect input:

    >>> w3lib.http.headers_raw_to_dict("Content-typt gzip\\n\\n")
    {}
    >>>

    Argument is ``None`` (return ``None``):

    >>> w3lib.http.headers_raw_to_dict(None)
    >>>

    """

    if headers_raw is None:
        return None
    return dict([
        (header_item[0].strip(), [header_item[1].strip()])
        for header_item
        in [
            header.split(':', 1)
            for header
            in headers_raw.splitlines()]
        if len(header_item) == 2])


def headers_dict_to_raw(headers_dict):
    """
    Returns a raw HTTP headers representation of headers

    For example:

    >>> import w3lib.http
    >>> w3lib.http.headers_dict_to_raw({'Content-type': 'text/html', 'Accept': 'gzip'}) # doctest: +SKIP
    'Content-type: text/html\\r\\nAccept: gzip'
    >>>

    Argument is ``None`` (returns ``None``):

    >>> w3lib.http.headers_dict_to_raw(None)
    >>>

    """

    if headers_dict is None:
        return None
    raw_lines = []
    for key, value in headers_dict.items():
        if isinstance(value, (str, unicode)):
            raw_lines.append("%s: %s" % (key, value))
        elif isinstance(value, (list, tuple)):
            for v in value:
                raw_lines.append("%s: %s" % (key, v))
    return '\r\n'.join(raw_lines)


def basic_auth_header(username, password):
    """
    Return an `Authorization` header field value for `HTTP Basic Access Authentication (RFC 2617)`_

    >>> import w3lib.http
    >>> w3lib.http.basic_auth_header('someuser', 'somepass')
    u'Basic c29tZXVzZXI6c29tZXBhc3M='

    .. _HTTP Basic Access Authentication (RFC 2617): http://www.ietf.org/rfc/rfc2617.txt

    """

    auth = "%s:%s" % (username, password)
    if not isinstance(auth, bytes):
        # XXX: RFC 2617 doesn't define encoding, but ISO-8859-1
        # seems to be the most widely used encoding here. See also:
        # http://greenbytes.de/tech/webdav/draft-ietf-httpauth-basicauth-enc-latest.html
        auth = auth.encode('ISO-8859-1')
    return 'Basic ' + urlsafe_b64encode(auth).decode('ascii')
