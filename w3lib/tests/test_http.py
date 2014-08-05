import unittest
from collections import OrderedDict
from w3lib.http import (basic_auth_header,
                        headers_dict_to_raw, headers_raw_to_dict)

__doctests__ = ['w3lib.http'] # for trial support

class HttpTests(unittest.TestCase):

    def test_basic_auth_header(self):
        self.assertEqual('Basic c29tZXVzZXI6c29tZXBhc3M=',
                basic_auth_header('someuser', 'somepass'))
        # Check url unsafe encoded header
        self.assertEqual('Basic c29tZXVzZXI6QDx5dTk-Jm8_UQ==',
            basic_auth_header('someuser', '@<yu9>&o?Q'))

    def test_headers_raw_to_dict(self):
        raw = b"Content-type: text/html\n\rAccept: gzip\n\n"
        dct = {b'Content-type': [b'text/html'], b'Accept': [b'gzip']}
        self.assertEqual(headers_raw_to_dict(raw), dct)

    def test_headers_dict_to_raw(self):
        dct = OrderedDict([
            (b'Content-type', b'text/html'),
            (b'Accept', b'gzip')
        ])
        self.assertEqual(
            headers_dict_to_raw(dct),
            b'Content-type: text/html\r\nAccept: gzip'
        )

        #Integer value found in a FTP response
        int_dct = OrderedDict([
            (b'Size', [12345]),
            (b'Accept', b'gzip')
        ])

        self.assertEqual(
            headers_dict_to_raw(int_dct),
            b'Size: 12345\r\nAccept: gzip'
        )

