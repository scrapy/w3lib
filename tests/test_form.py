# -*- coding: utf-8 -*-
from __future__ import absolute_import
import warnings
import unittest
from collections import OrderedDict
from w3lib.form import encode_multipart


class EncodeMultipartTest(unittest.TestCase):

    def test_encode_multipart(self):
        data = {'key': 'value'}
        with warnings.catch_warnings(record=True):
            body, boundary = encode_multipart(data)
        expected_body = (
            '\r\n--{boundary}'
            '\r\nContent-Disposition: form-data; name="key"\r\n'
            '\r\nvalue'
            '\r\n--{boundary}--'
            '\r\n'.format(boundary=boundary).encode('utf8')
        )
        self.assertEqual(body, expected_body)

    def test_encode_multipart_unicode(self):
        data = OrderedDict([
            ('ключ1', 'значение1'.encode('utf8')),
            ('ключ2', 'значение2'),
        ])
        with warnings.catch_warnings(record=True):
            body, boundary = encode_multipart(data)
        expected_body = (
            '\r\n--{boundary}'
            '\r\nContent-Disposition: form-data; name="ключ1"\r\n'
            '\r\nзначение1'
            '\r\n--{boundary}'
            '\r\nContent-Disposition: form-data; name="ключ2"\r\n'
            '\r\nзначение2'
            '\r\n--{boundary}--'
            '\r\n'.format(boundary=boundary).encode('utf8')
        )
        self.assertEqual(body, expected_body)

    def test_encode_multipart_file(self):
        # this data is not decodable using utf8
        data = {'key': ('file/name', b'\xa1\xa2\xa3\xa4\r\n\r')}
        with warnings.catch_warnings(record=True):
            body, boundary = encode_multipart(data)
        body_lines = [
            b'\r\n--' + boundary.encode('ascii'),
            b'\r\nContent-Disposition: form-data; name="key"; filename="file/name"\r\n',
            b'\r\n\xa1\xa2\xa3\xa4\r\n\r',
            b'\r\n--' + boundary.encode('ascii') + b'--\r\n',
        ]
        expected_body = b''.join(body_lines)
        self.assertEqual(body, expected_body)

    #def test_encode_multipart_int(self):
    #    data = {'key': 123}
    #    body, boundary = encode_multipart2(data)
    #    expected_body = (
    #        '\n--{boundary}'
    #        '\nContent-Disposition: form-data; name="key"\n'
    #        '\n123'
    #        '\n--{boundary}--'
    #        '\n'.format(boundary=boundary)
    #    )
    #    self.assertEqual(body, expected_body)
