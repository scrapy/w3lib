import pytest

from w3lib._util import iter_tag_attributes, to_unicode

with pytest.warns(DeprecationWarning, match="The w3lib.util module is deprecated."):
    from w3lib.util import to_bytes


class TestToBytesDeprecated:
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


class TestIterTagAttributes:
    @pytest.mark.parametrize(
        ("attrs", "expected"),
        [
            ("", []),
            ("   ", []),
            ("a=1 b=2", [("a", "1"), ("b", "2")]),
            ("a=\"1\" b='2' c=3", [("a", "1"), ("b", "2"), ("c", "3")]),
            # whitespace around the equals sign, and inside quoted values
            ('a = 1  b\t=\n"x y"', [("a", "1"), ("b", "x y")]),
            # names are lowercased, values are not
            ("HTTP-Equiv=Refresh", [("http-equiv", "Refresh")]),
            # valueless attributes are skipped, and so are stray characters
            ("a b=1 c / = d=2", [("b", "1"), ("d", "2")]),
            ("/ a=1 />", [("a", "1")]),
            # an empty value is still a value
            ("a=\"\" b='' c=", [("a", ""), ("b", ""), ("c", "")]),
            # whitespace after the equals sign is skipped, as in HTML
            ("a= b c=1", [("a", "b"), ("c", "1")]),
            # quotes that do not open a quoted value are ordinary characters
            ('a=b"c" d=\'e', [("a", "b"), ("d", "")]),
            # an unquoted value ends at whitespace or at a closing bracket
            ("a=1>b=2 c=3;x=4", [("a", "1"), ("b", "2"), ("c", "3;x=4")]),
            # a quoted value may contain what looks like other attributes
            ('a="b=1 c=2" d=3', [("a", "b=1 c=2"), ("d", "3")]),
            # repeated attributes are all yielded, in order
            ("a=1 a=2", [("a", "1"), ("a", "2")]),
        ],
    )
    def test_all(self, attrs, expected):
        assert list(iter_tag_attributes(attrs)) == expected

    def test_linear_on_crafted_input(self):
        # 100k attributes, both wanted and not, must not take super-linear time
        attrs = "http-equiv refresh " * 50000 + 'content="3; url=/next"'
        assert list(iter_tag_attributes(attrs)) == [("content", "3; url=/next")]
        assert len(list(iter_tag_attributes("a=1 " * 100000))) == 100000
