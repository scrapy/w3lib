"""
This module contains general purpose URL functions not found in the standard
library.
"""
import codecs
import os
import re
import posixpath
import warnings
import six
from six.moves.urllib.parse import (urljoin, urlsplit, urlunsplit,
                                    urldefrag, urlencode, urlparse,
                                    quote, parse_qs, parse_qsl)
from six.moves.urllib.request import pathname2url, url2pathname
from w3lib.util import to_bytes, to_native_str, to_unicode


# error handling function for bytes-to-Unicode decoding errors with URLs
def _quote_byte(error):
    return (to_unicode(quote(error.object[error.start:error.end])), error.end)

codecs.register_error('percentencode', _quote_byte)


# Python 2.x urllib.always_safe become private in Python 3.x;
# its content is copied here
_ALWAYS_SAFE_BYTES = (b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                      b'abcdefghijklmnopqrstuvwxyz'
                      b'0123456789' b'_.-')


def urljoin_rfc(base, ref, encoding='utf-8'):
    r"""
    .. warning::

        This function is deprecated and will be removed in future.
        Please use ``urlparse.urljoin`` instead.

    Same as urlparse.urljoin but supports unicode values in base and ref
    parameters (in which case they will be converted to str using the given
    encoding).

    Always returns a str.

    >>> import w3lib.url
    >>> w3lib.url.urljoin_rfc('http://www.example.com/path/index.html', u'/otherpath/index2.html')
    'http://www.example.com/otherpath/index2.html'
    >>>

    >>> w3lib.url.urljoin_rfc('http://www.example.com/path/index.html', u'fran\u00e7ais/d\u00e9part.htm')
    'http://www.example.com/path/fran\xc3\xa7ais/d\xc3\xa9part.htm'
    >>>


    """

    warnings.warn("w3lib.url.urljoin_rfc is deprecated, use urlparse.urljoin instead",
        DeprecationWarning)

    str_base = unicode_to_str(base, encoding)
    str_ref = unicode_to_str(ref, encoding)
    return urljoin(str_base, str_ref)

_reserved = b';/?:@&=+$|,#' # RFC 3986 (Generic Syntax)
_unreserved_marks = b"-_.!~*'()" # RFC 3986 sec 2.3
_safe_chars = _ALWAYS_SAFE_BYTES + b'%' + _reserved + _unreserved_marks

def safe_url_string(url, encoding='utf8', path_encoding='utf8'):
    """Convert the given URL into a legal URL by escaping unsafe characters
    according to RFC-3986.

    If a bytes URL is given, it is first converted to `str` using the given
    encoding (which defaults to 'utf-8'). 'utf-8' encoding is used for
    URL path component (unless overriden by path_encoding), and given
    encoding is used for query string or form data.
    When passing an encoding, you should use the encoding of the
    original page (the page from which the URL was extracted from).

    Calling this function on an already "safe" URL will return the URL
    unmodified.

    Always returns a native `str` (bytes in Python2, unicode in Python3).
    """
    # Python3's urlsplit() chokes on bytes input with non-ASCII chars,
    # so let's decode (to Unicode) using page encoding:
    #   - it is assumed that a raw bytes input comes from a document
    #     encoded with the supplied encoding (or UTF8 by default)
    #   - if the supplied (or default) encoding chokes,
    #     percent-encode offending bytes
    parts = urlsplit(to_unicode(url, encoding=encoding,
                                errors='percentencode'))

    # quote() in Python2 return type follows input type;
    # quote() in Python3 always returns Unicode (native str)
    return urlunsplit((
        to_native_str(parts.scheme),
        to_native_str(parts.netloc.encode('idna')),

        # default encoding for path component SHOULD be UTF-8
        quote(to_bytes(parts.path, path_encoding), _safe_chars),

        # encoding of query and fragment follows page encoding
        # or form-charset (if known and passed)
        quote(to_bytes(parts.query, encoding), _safe_chars),
        quote(to_bytes(parts.fragment, encoding), _safe_chars),
    ))

_parent_dirs = re.compile(r'/?(\.\./)+')

def safe_download_url(url):
    """ Make a url for download. This will call safe_url_string
    and then strip the fragment, if one exists. The path will
    be normalised.

    If the path is outside the document root, it will be changed
    to be within the document root.
    """
    safe_url = safe_url_string(url)
    scheme, netloc, path, query, _ = urlsplit(safe_url)
    if path:
        path = _parent_dirs.sub('', posixpath.normpath(path))
        if url.endswith('/') and not path.endswith('/'):
            path += '/'
    else:
        path = '/'
    return urlunsplit((scheme, netloc, path, query, ''))

def is_url(text):
    return text.partition("://")[0] in ('file', 'http', 'https')

def url_query_parameter(url, parameter, default=None, keep_blank_values=0):
    """Return the value of a url parameter, given the url and parameter name

    General case:

    >>> import w3lib.url
    >>> w3lib.url.url_query_parameter("product.html?id=200&foo=bar", "id")
    '200'
    >>>

    Return a default value if the parameter is not found:

    >>> w3lib.url.url_query_parameter("product.html?id=200&foo=bar", "notthere", "mydefault")
    'mydefault'
    >>>

    Returns None if `keep_blank_values` not set or 0 (default):

    >>> w3lib.url.url_query_parameter("product.html?id=", "id")
    >>>

    Returns an empty string if `keep_blank_values` set to 1:

    >>> w3lib.url.url_query_parameter("product.html?id=", "id", keep_blank_values=1)
    ''
    >>>

    """

    queryparams = parse_qs(
        urlsplit(str(url))[3],
        keep_blank_values=keep_blank_values
    )
    return queryparams.get(parameter, [default])[0]

def url_query_cleaner(url, parameterlist=(), sep='&', kvsep='=', remove=False, unique=True):
    """Clean URL arguments leaving only those passed in the parameterlist keeping order

    >>> import w3lib.url
    >>> w3lib.url.url_query_cleaner("product.html?id=200&foo=bar&name=wired", ('id',))
    'product.html?id=200'
    >>> w3lib.url.url_query_cleaner("product.html?id=200&foo=bar&name=wired", ['id', 'name'])
    'product.html?id=200&name=wired'
    >>>

    If `unique` is ``False``, do not remove duplicated keys

    >>> w3lib.url.url_query_cleaner("product.html?d=1&e=b&d=2&d=3&other=other", ['d'], unique=False)
    'product.html?d=1&d=2&d=3'
    >>>

    If `remove` is ``True``, leave only those **not in parameterlist**.

    >>> w3lib.url.url_query_cleaner("product.html?id=200&foo=bar&name=wired", ['id'], remove=True)
    'product.html?foo=bar&name=wired'
    >>> w3lib.url.url_query_cleaner("product.html?id=2&foo=bar&name=wired", ['id', 'foo'], remove=True)
    'product.html?name=wired'
    >>>

    """

    if isinstance(parameterlist, (six.text_type, bytes)):
        parameterlist = [parameterlist]
    url = urldefrag(url)[0]
    base, _, query = url.partition('?')
    seen = set()
    querylist = []
    for ksv in query.split(sep):
        k, _, _ = ksv.partition(kvsep)
        if unique and k in seen:
            continue
        elif remove and k in parameterlist:
            continue
        elif not remove and k not in parameterlist:
            continue
        else:
            querylist.append(ksv)
            seen.add(k)
    return '?'.join([base, sep.join(querylist)]) if querylist else base

def add_or_replace_parameter(url, name, new_value):
    """Add or remove a parameter to a given url

    >>> import w3lib.url
    >>> w3lib.url.add_or_replace_parameter('http://www.example.com/index.php', 'arg', 'v')
    'http://www.example.com/index.php?arg=v'
    >>> w3lib.url.add_or_replace_parameter('http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3', 'arg4', 'v4')
    'http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3&arg4=v4'
    >>> w3lib.url.add_or_replace_parameter('http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3', 'arg3', 'v3new')
    'http://www.example.com/index.php?arg1=v1&arg2=v2&arg3=v3new'
    >>>

    """
    parsed = urlsplit(url)
    args = parse_qsl(parsed.query, keep_blank_values=True)

    new_args = []
    found = False
    for name_, value_ in args:
        if name_ == name:
            new_args.append((name_, new_value))
            found = True
        else:
            new_args.append((name_, value_))

    if not found:
        new_args.append((name, new_value))

    query = urlencode(new_args)
    return urlunsplit(parsed._replace(query=query))


def path_to_file_uri(path):
    """Convert local filesystem path to legal File URIs as described in:
    http://en.wikipedia.org/wiki/File_URI_scheme
    """
    x = pathname2url(os.path.abspath(path))
    if os.name == 'nt':
        x = x.replace('|', ':') # http://bugs.python.org/issue5861
    return 'file:///%s' % x.lstrip('/')

def file_uri_to_path(uri):
    """Convert File URI to local filesystem path according to:
    http://en.wikipedia.org/wiki/File_URI_scheme
    """
    uri_path = urlparse(uri).path
    return url2pathname(uri_path)

def any_to_uri(uri_or_path):
    """If given a path name, return its File URI, otherwise return it
    unmodified
    """
    if os.path.splitdrive(uri_or_path)[0]:
        return path_to_file_uri(uri_or_path)
    u = urlparse(uri_or_path)
    return uri_or_path if u.scheme else path_to_file_uri(uri_or_path)
