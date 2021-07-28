import unittest
from collections import OrderedDict
from w3lib.http import (basic_auth_header,
                        headers_dict_to_raw, headers_raw_to_dict)

__doctests__ = ['w3lib.http'] # for trial support

class HttpTests(unittest.TestCase):

    def test_basic_auth_header(self):
        self.assertEqual(b'Basic c29tZXVzZXI6c29tZXBhc3M=',
                basic_auth_header('someuser', 'somepass'))
        # Check url unsafe encoded header
        self.assertEqual(b'Basic c29tZXVzZXI6QDx5dTk-Jm8_UQ==',
            basic_auth_header('someuser', '@<yu9>&o?Q'))

    def test_basic_auth_header_encoding(self):
        self.assertEqual(b'Basic c29tw6Z1c8Oocjpzw7htZXDDpHNz',
                basic_auth_header('somæusèr', 'sømepäss', encoding='utf8'))
        # default encoding (ISO-8859-1)
        self.assertEqual(b'Basic c29t5nVz6HI6c_htZXDkc3M=',
                basic_auth_header('somæusèr', 'sømepäss'))

    def test_headers_raw_dict_none(self):
        self.assertIsNone(headers_raw_to_dict(None))
        self.assertIsNone(headers_dict_to_raw(None))

    def test_headers_raw_to_dict(self):
        raw = b'\r\n'.join((b"Content-type: text/html",
                            b"Accept: gzip",
                            b"Cache-Control: no-cache",
                            b"Cache-Control: no-store"))
        dct = {b'Content-type': [b'text/html'], b'Accept': [b'gzip'],
               b'Cache-Control': [b'no-cache', b'no-store']}
        self.assertEqual(headers_raw_to_dict(raw), dct)

    def test_headers_raw_to_dict_multiline(self):
        raw = b'\r\n'.join((b'Content-Type: multipart/related;',
                            b'  type="application/xop+xml";',
                            b'\tboundary="example"',
                            b'Cache-Control: no-cache'))
        # With strict=False, the header value that spans across
        # multiple lines does not get parsed fully, and only the first
        # line is retained.
        dct = {b'Content-Type': [b'multipart/related;'],
               b'Cache-Control': [b'no-cache']}
        self.assertEqual(headers_raw_to_dict(raw), dct)

    def test_headers_raw_to_dict_multiline_strict(self):
        raw = b'\r\n'.join((b'Content-Type: multipart/related;',
                            b'  type="application/xop+xml";',
                            b'\tboundary="example"',
                            b'Cache-Control: no-cache'))
        # With strict=True, the header value that spans across
        # multiple lines does get parsed fully.
        dct = {
            b'Content-Type': [
                b'\r\n'.join((b'multipart/related;',
                              b'  type="application/xop+xml";',
                              b'\tboundary="example"'))
            ],
            b'Cache-Control': [b'no-cache']}
        self.assertEqual(headers_raw_to_dict(raw, strict=True), dct)

    def test_headers_dict_to_raw(self):
        dct = OrderedDict([
            (b'Content-type', b'text/html'),
            (b'Accept', b'gzip')
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b'Content-type: text/html\r\nAccept: gzip'
        )

    def test_headers_dict_to_raw_listtuple(self):
        dct = OrderedDict([
            (b'Content-type', [b'text/html']),
            (b'Accept', [b'gzip'])
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b'Content-type: text/html\r\nAccept: gzip'
        )

        dct = OrderedDict([
            (b'Content-type', (b'text/html',)),
            (b'Accept', (b'gzip',))
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b'Content-type: text/html\r\nAccept: gzip'
        )

        dct = OrderedDict([
            (b'Cookie', (b'val001', b'val002')),
            (b'Accept', b'gzip')
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b'Cookie: val001\r\nCookie: val002\r\nAccept: gzip'
        )

        dct = OrderedDict([
            (b'Cookie', [b'val001', b'val002']),
            (b'Accept', b'gzip')
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b'Cookie: val001\r\nCookie: val002\r\nAccept: gzip'
        )

    def test_headers_dict_to_raw_wrong_values(self):
        dct = OrderedDict([
            (b'Content-type', 0),
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b''
        )

        dct = OrderedDict([
            (b'Content-type', 1),
            (b'Accept', [b'gzip'])
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b'Accept: gzip'
        )
