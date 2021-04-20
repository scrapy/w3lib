from unittest import TestCase

from pytest import deprecated_call

from w3lib.util import str_to_unicode, to_native_str, unicode_to_str


class StrToUnicodeTestCase(TestCase):

    def test_deprecation(self):
        with deprecated_call():
            str_to_unicode('')


class ToNativeStrTestCase(TestCase):

    def test_deprecation(self):
        with deprecated_call():
            to_native_str('')


class UnicodeToStrTestCase(TestCase):

    def test_deprecation(self):
        with deprecated_call():
            unicode_to_str('')
