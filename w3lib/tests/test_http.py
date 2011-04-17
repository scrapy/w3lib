import unittest
from w3lib.http import basic_auth_header

__doctests__ = ['w3lib.http'] # for trial support

class HttpTests(unittest.TestCase):

    def test_basic_auth_header(self):
        self.assertEqual('Basic c29tZXVzZXI6c29tZXBhc3M=',
                basic_auth_header('someuser', 'somepass'))
        # Check url unsafe encoded header
        self.assertEqual('Basic c29tZXVzZXI6QDx5dTk-Jm8_UQ==',
            basic_auth_header('someuser', '@<yu9>&o?Q'))
