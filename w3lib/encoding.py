"""
Functions for handling encoding of web pages
"""
import re, codecs, encodings

_HEADER_ENCODING_RE = re.compile(r'charset=([\w-]+)', re.I)

def http_content_type_encoding(content_type):
    """Extract the encoding in the content-type header"""
    if content_type:
        match = _HEADER_ENCODING_RE.search(content_type)
        if match:
            return resolve_encoding(match.group(1))

# regexp for parsing HTTP meta tags
_TEMPLATE = r'''%s\s*=\s*["']?\s*%s\s*["']?'''
_HTTPEQUIV_RE = _TEMPLATE % ('http-equiv', 'Content-Type')
_CONTENT_RE = _TEMPLATE % ('content', r'(?P<mime>[^;]+);\s*charset=(?P<charset>[\w-]+)')
_CONTENT2_RE = _TEMPLATE % ('charset', r'(?P<charset2>[\w-]+)')
_XML_ENCODING_RE = _TEMPLATE % ('encoding', r'(?P<xmlcharset>[\w-]+)')

# check for meta tags, or xml decl. and stop search if a body tag is encountered
_BODY_ENCODING_RE = re.compile(
    r'<\s*(?:meta\s+(?:%s\s+%s|%s)|\?xml\s[^>]+%s|body)' % \
        (_HTTPEQUIV_RE, _CONTENT_RE, _CONTENT2_RE, _XML_ENCODING_RE), re.I)

def html_body_declared_encoding(html_body_str):
    """encoding specified in meta tags in the html body, or None if no 
    suitable encoding was found
    """
    # html5 suggests the first 1024 bytes are sufficient, we allow for more
    chunk = html_body_str[:4096]
    match = _BODY_ENCODING_RE.search(chunk)
    if match:
        encoding = match.group('charset') or match.group('charset2') \
                or match.group('xmlcharset')
        if encoding:
            return resolve_encoding(encoding)

# Default encoding translation
# this maps cannonicalized encodings to target encodings
# see http://www.whatwg.org/specs/web-apps/current-work/multipage/parsing.html#character-encodings-0
# in addition, gb18030 supercedes gb2312 & gbk
# the keys are converted using _c18n_encoding and in sorted order
DEFAULT_ENCODING_TRANSLATION = {
        'ascii': 'cp1252',
        'euc_kr': 'cp949',
        'gb2312': 'gb18030',
        'gbk': 'gb18030',
        'iso8859_11': 'cp874',
        'iso8859_9': 'cp1254',
        'latin_1': 'cp1252',
        'macintosh': 'mac_roman',
        'shift_jis': 'cp932',
        'tis_620': 'cp874',
        'win_1251': 'cp1251',
        'windows_31j': 'cp932',
        'win_31j': 'cp932',
        'windows_874': 'cp874',
        'win_874': 'cp874',
        'x_sjis': 'cp932',
        'zh_cn': 'gb18030'
}

def _c18n_encoding(encoding):
    """Cannonicalize an encoding name

    This performs normalization and translates aliases using python's 
    encoding aliases
    """
    normed = encodings.normalize_encoding(encoding).lower()
    return encodings.aliases.aliases.get(normed, normed)

def resolve_encoding(encoding_alias):
    """Return the encoding the given encoding alias maps to, or None if the
    encoding cannot be interpreted
    """
    c18n_encoding = _c18n_encoding(encoding_alias)
    translated = DEFAULT_ENCODING_TRANSLATION.get(c18n_encoding, c18n_encoding)
    try:
        return codecs.lookup(translated).name
    except LookupError:
        return None

_BOM_TABLE = [
    (codecs.BOM_UTF32_BE, 'utf-32-be'),
    (codecs.BOM_UTF32_LE, 'utf-32-le'),
    (codecs.BOM_UTF16_BE, 'utf-16-be'),
    (codecs.BOM_UTF16_LE, 'utf-16-le'),
    (codecs.BOM_UTF8, 'utf-8')
]
_FIRST_CHARS = set(c[0] for (c, _) in _BOM_TABLE)

def read_bom(data):
    """Read the byte order mark in the text, if present, and 
    return the encoding represented by the BOM and the BOM.

    If no BOM can be detected, (None, None) is returned.
    """
    # common case is no BOM, so this is fast
    if data[0] in _FIRST_CHARS:
        for bom, encoding in _BOM_TABLE:
            if data.startswith(bom):
                return encoding, bom
    return None, None

# Python decoder doesn't follow unicode standard when handling
# bad utf-8 encoded strings. see http://bugs.python.org/issue8271
codecs.register_error('w3lib_replace', lambda exc: (u'\ufffd', exc.start+1))

def to_unicode(data_str, encoding):
    """Convert a str object to unicode using the encoding given

    Characters that cannot be converted will be converted to '\ufffd' (the
    unicode replacement character).
    """
    data_str.decode(encoding, 'w3lib_replace')

def _enc_unicode(data_str, encoding):
    """convert the data_str to unicode inserting the unicode replacement
    character where necessary. 
    
    returns (encoding, unicode)
    """
    return encoding, data_str.decode(encoding, 'w3lib_replace')

def html_to_unicode(content_type_header, html_body_str, 
        default_encoding='utf8', auto_detect_fun=None):
    """Convert raw html bytes to unicode
    
    This attempts to make a reasonable guess at the content encoding of the
    html body, following a similar process as a web browser. 

    It will try in order:
    * http content type header
    * BOM (byte-order mark)
    * meta or xml tag declarations
    * auto-detection, if the `auto_detect_fun` keyword argument is not None
    * default encoding in keyword arg (which defaults to utf8)
    
    If an encoding other than the auto-detected or default encoding is used,
    overrides will be applied, converting some character encodings to more
    suitable alternatives.
    
    If a BOM is found matching the encoding, it will be stripped.
    
    The `auto_detect_fun` argument can be used to pass a function that will
    sniff the encoding of the text. This function must take the raw text as an
    argument and return the name of an encoding that python can process, or
    None.  To use chardet, for example, you can define the function as:
        auto_detect_fun=lambda x: chardet.detect(x).get('encoding')
    or to use UnicodeDammit (shipped with the BeautifulSoup library):
        auto_detect_fun=lambda x: UnicodeDammit(x).originalEncoding

    If the locale of the website or user language preference is known, then a
    better default encoding can be supplied.

    If the content type header is not present, None can be passed signifying
    that the header was not present.

    This method will not fail, if characters cannot be converted to unicode, 
    '\ufffd' (the unicode replacement character) will be inserted instead.

    returns a tuple of (encoding used, unicode)
    """
    enc = http_content_type_encoding(content_type_header)
    bom_enc, bom = read_bom(html_body_str)
    if enc is not None:
            # remove BOM if it agrees with the encoding
        if enc == bom_enc:
            html_body_str = html_body_str[len(bom):]
        elif enc == 'utf-16' or enc == 'utf-32':
            # read endianness from BOM, or default to big endian 
            # tools.ietf.org/html/rfc2781 section 4.3
            if bom_enc is not None and bom_enc.startswith(enc):
                enc = bom_enc
                html_body_str = html_body_str[len(bom):]
            else:
                enc += '-be'
        return _enc_unicode(html_body_str, enc)
    if bom_enc is not None:
        return _enc_unicode(html_body_str[len(bom):], bom_enc)
    enc = html_body_declared_encoding(html_body_str)
    if enc is None and (auto_detect_fun is not None):
        enc = auto_detect_fun(html_body_str)
    if enc is None:
        enc = default_encoding
    return _enc_unicode(html_body_str, enc)