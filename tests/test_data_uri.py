import unittest

from w3lib.data_uri import parse_data_uri


class DataURITests(unittest.TestCase):

    def test_default_mediatype_charset(self):
        type_, params, data = parse_data_uri("data:,A%20brief%20note")
        self.assertEqual(type_, "text/plain")
        self.assertEqual(params, {"charset": "US-ASCII"})
        self.assertEqual(data, b"A brief note")

    def test_default_mediatype(self):
        type_, params, data = parse_data_uri("data:;charset=iso-8859-7,"
                                             "%be%d3%be")
        self.assertEqual(type_, "text/plain")
        self.assertEqual(params, {"charset": "iso-8859-7"})
        self.assertEqual(data, b"\xbe\xd3\xbe")

    def test_text_charset(self):
        type_, params, data = parse_data_uri("data:text/plain;"
                                             "charset=iso-8859-7,"
                                             "%be%d3%be")
        self.assertEqual(type_, "text/plain")
        self.assertEqual(params, {"charset": "iso-8859-7"})
        self.assertEqual(data, b"\xbe\xd3\xbe")

    def test_mediatype_parameters(self):
        type_, params, data = parse_data_uri('data:text/plain;'
                                             'foo=%22foo;bar%5C%22%22;'
                                             'charset=utf-8;'
                                             'bar=%22foo;%5C%22 foo ;/,%22,'
                                             '%CE%8E%CE%A3%CE%8E')

        self.assertEqual(type_, "text/plain")
        self.assertEqual(params, {"charset": "utf-8",
                                  "foo": 'foo;bar"',
                                  "bar": 'foo;" foo ;/,'})
        self.assertEqual(data, b"\xce\x8e\xce\xa3\xce\x8e")

    def test_base64(self):
        type_, params, data = parse_data_uri("data:text/plain;base64,"
                                             "SGVsbG8sIHdvcmxkLg%3D%3D")
        self.assertEqual(type_, "text/plain")
        self.assertEqual(data, b"Hello, world.")

    def test_wrong_base64_param(self):
        with self.assertRaises(ValueError):
            parse_data_uri("data:text/plain;baes64,SGVsbG8sIHdvcmxkLg%3D%3D")

    def test_wrong_scheme(self):
        with self.assertRaises(ValueError):
            parse_data_uri("http://example.com/")
