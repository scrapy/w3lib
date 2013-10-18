"""
Functions for dealing with markup text
"""

import re
import six
from six import moves

from w3lib.util import str_to_unicode, unicode_to_str
from w3lib.url import safe_url_string

_ent_re = re.compile(r'&(#?(x?))([^&;\s]+);')
_tag_re = re.compile(r'<[a-zA-Z\/!].*?>', re.DOTALL)
_baseurl_re = re.compile(six.u(r'<base\s+href\s*=\s*[\"\']\s*([^\"\'\s]+)\s*[\"\']'), re.I)
_meta_refresh_re = re.compile(six.u(r'<meta[^>]*http-equiv[^>]*refresh[^>]*content\s*=\s*(?P<quote>["\'])(?P<int>(\d*\.)?\d+)\s*;\s*url=(?P<url>.*?)(?P=quote)'), re.DOTALL | re.IGNORECASE)
_cdata_re = re.compile(r'((?P<cdata_s><!\[CDATA\[)(?P<cdata_d>.*?)(?P<cdata_e>\]\]>))', re.DOTALL)

def remove_entities(text, keep=(), remove_illegal=True, encoding='utf-8'):
    """Remove entities from the given text by converting them to
    corresponding unicode character.

    'text' can be a unicode string or a byte string encoded in the given
    `encoding` (which defaults to 'utf-8').

    If 'keep' is passed (with a list of entity names) those entities will
    be kept (they won't be removed).

    It supports both numeric (&#nnnn; and &#hhhh;) and named (&nbsp; &gt;)
    entities.

    If remove_illegal is True, entities that can't be converted are removed.
    If remove_illegal is False, entities that can't be converted are kept "as
    is". For more information see the tests.

    Always returns a unicode string (with the entities removed).
    """

    def convert_entity(m):
        entity_body = m.group(3)
        if m.group(1):
            try:
                if m.group(2):
                    number = int(entity_body, 16)
                else:
                    number = int(entity_body, 10)
                # Numeric character references in the 80-9F range are typically
                # interpreted by browsers as representing the characters mapped
                # to bytes 80-9F in the Windows-1252 encoding. For more info
                # see: http://en.wikipedia.org/wiki/Character_encodings_in_HTML
                if 0x80 <= number <= 0x9f:
                    return six.int2byte(number).decode('cp1252')
            except ValueError:
                number = None
        else:
            if entity_body in keep:
                return m.group(0)
            else:
                number = moves.html_entities.name2codepoint.get(entity_body)
        if number is not None:
            try:
                return six.unichr(number)
            except ValueError:
                pass

        return u'' if remove_illegal else m.group(0)

    return _ent_re.sub(convert_entity, str_to_unicode(text, encoding))

def has_entities(text, encoding=None):
    return bool(_ent_re.search(str_to_unicode(text, encoding)))

def replace_tags(text, token='', encoding=None):
    """Replace all markup tags found in the given text by the given token. By
    default token is a null string so it just remove all tags.

    'text' can be a unicode string or a regular string encoded as 'utf-8'

    Always returns a unicode string.
    """
    return _tag_re.sub(token, str_to_unicode(text, encoding))


_REMOVECOMMENTS_RE = re.compile(u'<!--.*?-->', re.DOTALL)
def remove_comments(text, encoding=None):
    """ Remove HTML Comments. """
    text = str_to_unicode(text, encoding)
    return _REMOVECOMMENTS_RE.sub(u'', text)

def remove_tags(text, which_ones=(), keep=(), encoding=None):
    """ Remove HTML Tags only.

        which_ones and keep are both tuples, there are four cases:

        which_ones, keep (1 - not empty, 0 - empty)
        1, 0 - remove all tags in which_ones
        0, 1 - remove all tags except the ones in keep
        0, 0 - remove all tags
        1, 1 - not allowd
    """

    assert not (which_ones and keep), 'which_ones and keep can not be given at the same time'

    def will_remove(tag):
        if which_ones:
            return tag in which_ones
        else:
            return tag not in keep

    def remove_tag(m):
        tag = m.group(1)
        return u'' if will_remove(tag) else m.group(0)

    regex = '</?([^ >/]+).*?>'
    retags = re.compile(regex, re.DOTALL | re.IGNORECASE)

    return retags.sub(remove_tag, str_to_unicode(text, encoding))

def remove_tags_with_content(text, which_ones=(), encoding=None):
    """ Remove tags and its content.

        which_ones -- is a tuple of which tags with its content we want to remove.
                      if is empty do nothing.
    """
    text = str_to_unicode(text, encoding)
    if which_ones:
        tags = '|'.join([r'<%s.*?</%s>|<%s\s*/>' % (tag, tag, tag) for tag in which_ones])
        retags = re.compile(tags, re.DOTALL | re.IGNORECASE)
        text = retags.sub(u'', text)
    return text


def replace_escape_chars(text, which_ones=('\n', '\t', '\r'), replace_by=u'', \
        encoding=None):
    """ Remove escape chars. Default : \\n, \\t, \\r

        which_ones -- is a tuple of which escape chars we want to remove.
                      By default removes \n, \t, \r.

        replace_by -- text to replace the escape chars for.
                      It defaults to '', so the escape chars are removed.
    """
    text = str_to_unicode(text, encoding)
    for ec in which_ones:
        text = text.replace(ec, str_to_unicode(replace_by, encoding))
    return text

def unquote_markup(text, keep=(), remove_illegal=True, encoding=None):
    """
    This function receives markup as a text (always a unicode string or a utf-8 encoded string) and does the following:
     - removes entities (except the ones in 'keep') from any part of it that it's not inside a CDATA
     - searches for CDATAs and extracts their text (if any) without modifying it.
     - removes the found CDATAs
    """

    def _get_fragments(txt, pattern):
        offset = 0
        for match in pattern.finditer(txt):
            match_s, match_e = match.span(1)
            yield txt[offset:match_s]
            yield match
            offset = match_e
        yield txt[offset:]

    text = str_to_unicode(text, encoding)
    ret_text = u''
    for fragment in _get_fragments(text, _cdata_re):
        if isinstance(fragment, six.string_types):
            # it's not a CDATA (so we try to remove its entities)
            ret_text += remove_entities(fragment, keep=keep, remove_illegal=remove_illegal)
        else:
            # it's a CDATA (so we just extract its content)
            ret_text += fragment.group('cdata_d')
    return ret_text

def get_base_url(text, baseurl='', encoding='utf-8'):
    """Return the base url if declared in the given html text, relative to the
    given base url. If no base url is found, the given base url is returned
    """
    text = str_to_unicode(text, encoding)
    baseurl = unicode_to_str(baseurl, encoding)
    m = _baseurl_re.search(text)
    if m:
        baseurl = moves.urllib.parse.urljoin(baseurl, m.group(1).encode(encoding))
    return safe_url_string(baseurl)

def get_meta_refresh(text, baseurl='', encoding='utf-8'):
    """Return  the http-equiv parameter of the HTML meta element from the given
    HTML text and return a tuple (interval, url) where interval is an integer
    containing the delay in seconds (or zero if not present) and url is a
    string with the absolute url to redirect.

    If no meta redirect is found, (None, None) is returned.
    """
    if six.PY2:
        baseurl = unicode_to_str(baseurl, encoding)
    try:
        text = str_to_unicode(text, encoding)
    except UnicodeDecodeError:
        print(text)
        raise
    text = remove_comments(remove_entities(text))
    m = _meta_refresh_re.search(text)
    if m:
        interval = float(m.group('int'))
        url = safe_url_string(m.group('url').strip(' "\''), encoding)
        url = moves.urllib.parse.urljoin(baseurl, url)
        return interval, url
    else:
        return None, None
