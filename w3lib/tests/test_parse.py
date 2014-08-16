import unittest
import w3lib.parse


class ParseTests(unittest.TestCase):

    def test_parse_qs(self):
        self.assertEqual(
            w3lib.parse.parse_qs(
                b'a=2&poundsign=%C2%A3&eurosign=%E2%82%AC&price+in+%C2%A3=%C2%A3+1000&a=1'
            ), {
                b'a': [b'2', b'1'],
                b'eurosign': [b'\xe2\x82\xac'],
                b'poundsign': [b'\xc2\xa3'],
                b'price in \xc2\xa3': [b'\xc2\xa3 1000'],
            }
        )
        self.assertEqual(
            w3lib.parse.parse_qs(
                u'a=2&poundsign=%C2%A3&eurosign=%E2%82%AC&price+in+%C2%A3=%C2%A3+1000&a=1'
            ), {
                u'a': [u'2', u'1'],
                u'poundsign': [u'\u00a3'],
                u'eurosign': [u'\u20ac'],
                u'price in \u00a3': [u'\u00a3 1000'],
            }
        )

    def test_parse_qsl(self):
        self.assertEqual(
            w3lib.parse.parse_qsl(
                b'a=2&poundsign=%C2%A3&eurosign=%E2%82%AC&price+in+%C2%A3=%C2%A3+1000&a=1'
            ), [
                (b'a', b'2'),
                (b'poundsign', b'\xc2\xa3'),
                (b'eurosign', b'\xe2\x82\xac'),
                (b'price in \xc2\xa3', b'\xc2\xa3 1000'),
                (b'a', b'1'),
            ]
        )
        self.assertEqual(
            w3lib.parse.parse_qsl(
                u'a=2&poundsign=%C2%A3&eurosign=%E2%82%AC&price+in+%C2%A3=%C2%A3+1000&a=1'
            ), [
                (u'a', u'2'),
                (u'poundsign', u'\u00a3'),
                (u'eurosign', u'\u20ac'),
                (u'price in \u00a3', u'\u00a3 1000'),
                (u'a', u'1'),
            ]
        )
