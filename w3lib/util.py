from warnings import warn


def str_to_unicode(text, encoding=None, errors='strict'):
    warn(
        "The w3lib.utils.str_to_unicode function is deprecated and "
        "will be removed in a future release.",
        DeprecationWarning
    )
    if encoding is None:
        encoding = 'utf-8'
    if isinstance(text, bytes):
        return text.decode(encoding, errors)
    return text

def unicode_to_str(text, encoding=None, errors='strict'):
    warn(
        "The w3lib.utils.unicode_to_str function is deprecated and "
        "will be removed in a future release.",
        DeprecationWarning
    )
    if encoding is None:
        encoding = 'utf-8'
    if isinstance(text, str):
        return text.encode(encoding, errors)
    return text

def to_unicode(text, encoding=None, errors='strict'):
    """Return the unicode representation of a bytes object `text`. If `text`
    is already an unicode object, return it as-is."""
    if isinstance(text, str):
        return text
    if not isinstance(text, (bytes, str)):
        raise TypeError('to_unicode must receive a bytes, str or unicode '
                        'object, got %s' % type(text).__name__)
    if encoding is None:
        encoding = 'utf-8'
    return text.decode(encoding, errors)

def to_bytes(text, encoding=None, errors='strict'):
    """Return the binary representation of `text`. If `text`
    is already a bytes object, return it as-is."""
    if isinstance(text, bytes):
        return text
    if not isinstance(text, str):
        raise TypeError('to_bytes must receive a unicode, str or bytes '
                        'object, got %s' % type(text).__name__)
    if encoding is None:
        encoding = 'utf-8'
    return text.encode(encoding, errors)

def to_native_str(text, encoding=None, errors='strict'):
    """ Return str representation of `text` """
    warn(
        "The w3lib.utils.to_native_str function is deprecated and "
        "will be removed in a future release. Please use "
        "w3lib.utils.to_unicode instead.",
        DeprecationWarning
    )
    return to_unicode(text, encoding, errors)
