import unittest, codecs
from w3lib.encoding import (html_body_declared_encoding, read_bom, to_unicode,
        http_content_type_encoding, resolve_encoding, html_to_unicode)

class RequestEncodingTests(unittest.TestCase):
    def test_bom(self):
        # cjk water character in unicode
        water_unicode = u'\u6C34'
        # BOM + water character encoded
        utf16be = '\xfe\xff\x6c\x34'
        utf16le = '\xff\xfe\x34\x6c'
        utf32be = '\x00\x00\xfe\xff\x00\x00\x6c\x34'
        utf32le = '\xff\xfe\x00\x00\x34\x6c\x00\x00'
        for string in (utf16be, utf16le, utf32be, utf32le):
            bom_encoding, bom = read_bom(string)
            decoded = string[len(bom):].decode(bom_encoding)
            self.assertEqual(water_unicode, decoded)
        # Body without BOM
        enc, bom = read_bom("foo")
        self.assertEqual(enc, None)
        self.assertEqual(bom, None)
        # Empty body
        enc, bom = read_bom("")
        self.assertEqual(enc, None)
        self.assertEqual(bom, None)

    def test_http_encoding_header(self):
        header_value = "Content-Type: text/html; charset=ISO-8859-4"
        extracted = http_content_type_encoding(header_value)
        self.assertEqual(extracted, "iso8859-4")
        self.assertEqual(None, http_content_type_encoding("something else"))

    def test_html_body_declared_encoding(self):
        fragments = [
            # Content-Type as meta http-equiv
            """<meta http-equiv="content-type" content="text/html;charset=UTF-8" />""",
            """\n<meta http-equiv="Content-Type"\ncontent="text/html; charset=utf-8">""",
            """<meta content="text/html; charset=utf-8"\n http-equiv='Content-Type'>""",
            """ bad html still supported < meta http-equiv='Content-Type'\n content="text/html; charset=utf-8">""",
            # html5 meta charset
            """<meta charset="utf-8">""",
            # xml encoding
            """<?xml version="1.0" encoding="utf-8"?>""",
        ]
        for fragment in fragments:
            encoding = html_body_declared_encoding(fragment)
            self.assertEqual(encoding, 'utf-8', fragment)
        self.assertEqual(None, html_body_declared_encoding("something else"))
        self.assertEqual(None, html_body_declared_encoding("""
            <head></head><body>
            this isn't searched
            <meta charset="utf-8">
        """))
        self.assertEqual(None, html_body_declared_encoding(
            """<meta http-equiv="Fake-Content-Type-Header" content="text/html; charset=utf-8">"""))

class CodecsEncodingTestCase(unittest.TestCase):
    def test_resolve_encoding(self):
        self.assertEqual(resolve_encoding('latin1'), 'cp1252')
        self.assertEqual(resolve_encoding(' Latin-1'), 'cp1252')
        self.assertEqual(resolve_encoding('gb_2312-80'), 'gb18030')
        self.assertEqual(resolve_encoding('unknown encoding'), None)


class UnicodeDecodingTestCase(unittest.TestCase):

    def test_utf8(self):
        self.assertEqual(to_unicode('\xc2\xa3', 'utf-8'), u'\xa3')

    def test_invalid_utf8(self):
        self.assertEqual(to_unicode('\xc2\xc2\xa3', 'utf-8'), u'\ufffd\xa3')


def ct(charset):
    return "Content-Type: text/html; charset=" + charset if charset else None

def norm_encoding(enc):
    return codecs.lookup(enc).name

class HtmlConversionTests(unittest.TestCase):

    def test_unicode_body(self):
        unicode_string = u'\u043a\u0438\u0440\u0438\u043b\u043b\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0442\u0435\u043a\u0441\u0442'
        original_string = unicode_string.encode('cp1251')
        encoding, body_unicode = html_to_unicode(ct('cp1251'), original_string)
        # check body_as_unicode
        self.assertTrue(isinstance(body_unicode, unicode))
        self.assertEqual(body_unicode, unicode_string)

    def _assert_encoding(self, content_type, body, expected_encoding,
                expected_unicode):
        encoding, body_unicode = html_to_unicode(ct(content_type), body)
        self.assertTrue(isinstance(body_unicode, unicode))
        self.assertEqual(norm_encoding(encoding),
                norm_encoding(expected_encoding))
        self.assertEqual(body_unicode, expected_unicode)

    def test_content_type_and_conversion(self):
        """Test content type header is interpreted and text converted as
        expected
        """
        self._assert_encoding('utf-8', "\xc2\xa3", 'utf-8', u"\xa3")
        # something like this in the scrapy tests - but that's invalid?
        # self._assert_encoding('', "\xa3", 'utf-8', u"\xa3")
        # iso-8859-1 is overridden to cp1252
        self._assert_encoding('iso-8859-1', "\xa3", 'cp1252', u"\xa3")
        self._assert_encoding('', "\xc2\xa3", 'utf-8', u"\xa3")
        self._assert_encoding('none', "\xc2\xa3", 'utf-8', u"\xa3")
        self._assert_encoding('gb2312', "\xa8D", 'gb18030', u"\u2015")
        self._assert_encoding('gbk', "\xa8D", 'gb18030', u"\u2015")

    def test_invalid_utf8_encoded_body_with_valid_utf8_BOM(self):
        # unlike scrapy, the BOM is stripped
        self._assert_encoding('utf-8', "\xef\xbb\xbfWORD\xe3\xab",
                'utf-8',u'WORD\ufffd\ufffd')
        self._assert_encoding(None, "\xef\xbb\xbfWORD\xe3\xab",
                'utf-8',u'WORD\ufffd\ufffd')

    def test_replace_wrong_encoding(self):
        """Test invalid chars are replaced properly"""
        encoding, body_unicode = html_to_unicode(ct('utf-8'),
                'PREFIX\xe3\xabSUFFIX')
        # XXX: Policy for replacing invalid chars may suffer minor variations
        # but it should always contain the unicode replacement char (u'\ufffd')
        assert u'\ufffd' in body_unicode, repr(body_unicode)
        assert u'PREFIX' in body_unicode, repr(body_unicode)
        assert u'SUFFIX' in body_unicode, repr(body_unicode)

        # Do not destroy html tags due to encoding bugs
        encoding, body_unicode = html_to_unicode(ct('utf-8'),
            '\xf0<span>value</span>')
        assert u'<span>value</span>' in body_unicode, repr(body_unicode)

    def _assert_encoding_detected(self, content_type, expected_encoding, body,
            **kwargs):
        encoding, body_unicode  = html_to_unicode(ct(content_type), body, **kwargs)
        self.assertTrue(isinstance(body_unicode, unicode))
        self.assertEqual(norm_encoding(encoding),  norm_encoding(expected_encoding))

    def test_BOM(self):
        # utf-16 cases already tested, as is the BOM detection function

        # http header takes precedence, irrespective of BOM
        bom_be_str = codecs.BOM_UTF16_BE + u"hi".encode('utf-16-be')
        expected = u'\ufffd\ufffd\x00h\x00i'
        self._assert_encoding('utf-8', bom_be_str, 'utf-8', expected)

        # BOM is stripped when it agrees with the encoding, or used to
        # determine encoding
        bom_utf8_str = codecs.BOM_UTF8 + 'hi'
        self._assert_encoding('utf-8', bom_utf8_str, 'utf-8', u"hi")
        self._assert_encoding(None, bom_utf8_str, 'utf-8', u"hi")

    def test_utf16_32(self):
        # tools.ietf.org/html/rfc2781 section 4.3

        # USE BOM and strip it
        bom_be_str = codecs.BOM_UTF16_BE + u"hi".encode('utf-16-be')
        self._assert_encoding('utf-16', bom_be_str, 'utf-16-be', u"hi")
        self._assert_encoding(None, bom_be_str, 'utf-16-be', u"hi")

        bom_le_str = codecs.BOM_UTF16_LE + u"hi".encode('utf-16-le')
        self._assert_encoding('utf-16', bom_le_str, 'utf-16-le', u"hi")
        self._assert_encoding(None, bom_le_str, 'utf-16-le', u"hi")

        bom_be_str = codecs.BOM_UTF32_BE + u"hi".encode('utf-32-be')
        self._assert_encoding('utf-32', bom_be_str, 'utf-32-be', u"hi")
        self._assert_encoding(None, bom_be_str, 'utf-32-be', u"hi")

        bom_le_str = codecs.BOM_UTF32_LE + u"hi".encode('utf-32-le')
        self._assert_encoding('utf-32', bom_le_str, 'utf-32-le', u"hi")
        self._assert_encoding(None, bom_le_str, 'utf-32-le', u"hi")

        # if there is no BOM,  big endian should be chosen
        self._assert_encoding('utf-16', u"hi".encode('utf-16-be'), 'utf-16-be', u"hi")
        self._assert_encoding('utf-32', u"hi".encode('utf-32-be'), 'utf-32-be', u"hi")

    def test_html_encoding(self):
        # extracting the encoding from raw html is tested elsewhere
        body = """blah blah < meta   http-equiv="Content-Type"
            content="text/html; charset=iso-8859-1"> other stuff"""
        self._assert_encoding_detected(None, 'cp1252', body)

        # header encoding takes precedence
        self._assert_encoding_detected('utf-8', 'utf-8', body)
        # BOM encoding takes precedence
        self._assert_encoding_detected(None, 'utf-8', codecs.BOM_UTF8 + body)

    def test_autodetect(self):
        asciif = lambda x: 'ascii'
        body = """<meta charset="utf-8">"""
        # body encoding takes precedence
        self._assert_encoding_detected(None, 'utf-8', body,
                auto_detect_fun=asciif)
        # if no other encoding, the auto detect encoding is used.
        self._assert_encoding_detected(None, 'ascii', "no encoding info",
                auto_detect_fun=asciif)

    def test_default_encoding(self):
        # if no other method available, the default encoding of utf-8 is used
        self._assert_encoding_detected(None, 'utf-8', "no encoding info")
        # this can be overridden
        self._assert_encoding_detected(None, 'ascii', "no encoding info",
                default_encoding='ascii')

    def test_empty_body(self):
        # if no other method available, the default encoding of utf-8 is used
        self._assert_encoding_detected(None, 'utf-8', "")
