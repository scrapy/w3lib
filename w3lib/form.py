import six
if six.PY2:
    from cStringIO import StringIO as BytesIO
else:
    from io import BytesIO
from w3lib.util import unicode_to_str


def encode_multipart(data):
    """Encode the given data to be used in a multipart HTTP POST. Data is a
    where keys are the field name, and values are either strings or tuples
    (filename, content) for file uploads.

    This code is based on distutils.command.upload.

    Return (body, boundary) tuple where ``body`` is binary body value,
    and ``boundary`` is the boundary used (as native string).
    """
    # Build up the MIME payload for the POST data
    boundary = '--------------GHSKFJDLGDS7543FJKLFHRE75642756743254'
    sep_boundary = b'\r\n--' + boundary.encode('ascii')
    end_boundary = sep_boundary + b'--'
    body = BytesIO()
    for key, value in data.items():
        title = u'\r\nContent-Disposition: form-data; name="%s"' % key
        # handle multiple entries for the same name
        if type(value) != type([]):
            value = [value]
        for value in value:
            if type(value) is tuple:
                title += u'; filename="%s"' % value[0]
                value = value[1]
            else:
                value = unicode_to_str(value)  # in distutils: str(value).encode('utf-8')
            body.write(sep_boundary)
            body.write(title.encode('utf-8'))
            body.write(b"\r\n\r\n")
            body.write(value)
    body.write(end_boundary)
    body.write(b"\r\n")
    return body.getvalue(), boundary
