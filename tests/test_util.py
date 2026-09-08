import pytest

from w3lib.util import to_bytes, to_unicode


class TestToBytes:
    def test_type_error(self):
        with pytest.raises(TypeError):
            to_bytes(True)  # type: ignore[arg-type]

    def test_bytes_passthrough(self):
        data = b"caf\xe9"
        assert to_bytes(data) is data

    def test_str(self):
        assert to_bytes("café") == b"caf\xc3\xa9"

    def test_encoding(self):
        assert to_bytes("café", encoding="latin1") == b"caf\xe9"

    def test_errors(self):
        with pytest.raises(UnicodeEncodeError):
            to_bytes("café", encoding="ascii")
        assert to_bytes("café", encoding="ascii", errors="replace") == b"caf?"


class TestToUnicode:
    def test_type_error(self):
        with pytest.raises(TypeError):
            to_unicode(True)  # type: ignore[arg-type]

    def test_str_passthrough(self):
        data = "café"
        assert to_unicode(data) is data

    def test_bytes(self):
        assert to_unicode(b"caf\xc3\xa9") == "café"

    def test_encoding(self):
        assert to_unicode(b"caf\xe9", encoding="latin1") == "café"

    def test_errors(self):
        with pytest.raises(UnicodeDecodeError):
            to_unicode(b"caf\xe9")
        assert to_unicode(b"caf\xe9", errors="replace") == "caf\ufffd"
