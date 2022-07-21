from unittest import TestCase

from pytest import deprecated_call, raises

from w3lib.util import (
    str_to_unicode,
    to_bytes,
    to_native_str,
    to_unicode,
    unicode_to_str,
)


class StrToUnicodeTestCase(TestCase):
    def test_deprecation(self):
        with deprecated_call():
            str_to_unicode("")


class ToBytesTestCase(TestCase):
    def test_type_error(self):
        with raises(TypeError):
            to_bytes(True)  # type: ignore


class ToNativeStrTestCase(TestCase):
    def test_deprecation(self):
        with deprecated_call():
            to_native_str("")


class ToUnicodeTestCase(TestCase):
    def test_type_error(self):
        with raises(TypeError):
            to_unicode(True)  # type: ignore


class UnicodeToStrTestCase(TestCase):
    def test_deprecation(self):
        with deprecated_call():
            unicode_to_str("")
