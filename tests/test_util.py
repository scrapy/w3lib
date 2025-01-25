from unittest import TestCase

from pytest import raises

from w3lib.util import to_bytes, to_unicode


class ToBytesTestCase(TestCase):
    def test_type_error(self):
        with raises(TypeError):
            to_bytes(True)  # type: ignore


class ToUnicodeTestCase(TestCase):
    def test_type_error(self):
        with raises(TypeError):
            to_unicode(True)  # type: ignore
