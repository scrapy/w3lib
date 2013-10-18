"""
This module contains general purpose URL functions not found in the standard
library.
"""
import os
import re
import posixpath
import warnings
from six import moves
from w3lib.util import unicode_to_str

# Python 2.x urllib.always_safe become private in Python 3.x;
# its content is copied here
_ALWAYS_SAFE_BYTES = (b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                      b'abcdefghijklmnopqrstuvwxyz'
                      b'0123456789' b'_.-')


def urljoin_rfc(base, ref, encoding='utf-8'):
    """Same as urlparse.urljoin but supports unicode values in base and ref
    parameters (in which case they will be converted to str using the given
    encoding).

    Always returns a str.
    """
    warnings.warn("w3lib.url.urljoin_rfc is deprecated, use urlparse.urljoin instead",
        DeprecationWarning)

    str_base = unicode_to_str(base, encoding)
    str_ref = unicode_to_str(ref, encoding)
    return moves.urllib.parse.urljoin(str_base, str_ref)

_reserved = b';/?:@&=+$|,#' # RFC 3986 (Generic Syntax)
_unreserved_marks = b"-_.!~*'()" # RFC 3986 sec 2.3
_safe_chars = _ALWAYS_SAFE_BYTES + b'%' + _reserved + _unreserved_marks

def safe_url_string(url, encoding='utf8'):
    """Convert the given url into a legal URL by escaping unsafe characters
    according to RFC-3986.

    If a unicode url is given, it is first converted to str using the given
    encoding (which defaults to 'utf-8'). When passing a encoding, you should
    use the encoding of the original page (the page from which the url was
    extracted from).

    Calling this function on an already "safe" url will return the url
    unmodified.

    Always returns a str.
    """
    s = unicode_to_str(url, encoding)
    return moves.urllib.parse.quote(s, _safe_chars)


_parent_dirs = re.compile(r'/?(\.\./)+')

def safe_download_url(url):
    """ Make a url for download. This will call safe_url_string
    and then strip the fragment, if one exists. The path will
    be normalised.

    If the path is outside the document root, it will be changed
    to be within the document root.
    """
    safe_url = safe_url_string(url)
    scheme, netloc, path, query, _ = moves.urllib.parse.urlsplit(safe_url)
    if path:
        path = _parent_dirs.sub('', posixpath.normpath(path))
        if url.endswith('/') and not path.endswith('/'):
            path += '/'
    else:
        path = '/'
    return moves.urllib.parse.urlunsplit((scheme, netloc, path, query, ''))

def is_url(text):
    return text.partition("://")[0] in ('file', 'http', 'https')

def url_query_parameter(url, parameter, default=None, keep_blank_values=0):
    """Return the value of a url parameter, given the url and parameter name"""
    queryparams = moves.urllib.parse.parse_qs(
        moves.urllib.parse.urlsplit(str(url))[3],
        keep_blank_values=keep_blank_values
    )
    return queryparams.get(parameter, [default])[0]

def url_query_cleaner(url, parameterlist=(), sep='&', kvsep='=', remove=False, unique=True):
    """Clean url arguments leaving only those passed in the parameterlist keeping order

    If remove is True, leave only those not in parameterlist.
    If unique is False, do not remove duplicated keys
    """
    url = moves.urllib.parse.urldefrag(url)[0]
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

def add_or_replace_parameter(url, name, new_value, sep='&', url_is_quoted=False):
    """Add or remove a parameter to a given url"""
    def has_querystring(url):
        _, _, _, query, _ = moves.urllib.parse.urlsplit(url)
        return bool(query)

    parameter = url_query_parameter(url, name, keep_blank_values=1)
    if url_is_quoted:
        parameter = moves.urllib.parse.quote(parameter)
    if parameter is None:
        if has_querystring(url):
            next_url = url + sep + name + '=' + new_value
        else:
            next_url = url.rstrip('?') + '?' + name + '=' + new_value
    else:
        next_url = url.replace(name+'='+parameter,
                               name+'='+new_value)
    return next_url

def path_to_file_uri(path):
    """Convert local filesystem path to legal File URIs as described in:
    http://en.wikipedia.org/wiki/File_URI_scheme
    """
    x = moves.urllib.request.pathname2url(os.path.abspath(path))
    if os.name == 'nt':
        x = x.replace('|', ':') # http://bugs.python.org/issue5861
    return 'file:///%s' % x.lstrip('/')

def file_uri_to_path(uri):
    """Convert File URI to local filesystem path according to:
    http://en.wikipedia.org/wiki/File_URI_scheme
    """
    uri_path = moves.urllib.parse.urlparse(uri).path
    return moves.urllib.request.url2pathname(uri_path)

def any_to_uri(uri_or_path):
    """If given a path name, return its File URI, otherwise return it
    unmodified
    """
    if os.path.splitdrive(uri_or_path)[0]:
        return path_to_file_uri(uri_or_path)
    u = moves.urllib.parse.urlparse(uri_or_path)
    return uri_or_path if u.scheme else path_to_file_uri(uri_or_path)
