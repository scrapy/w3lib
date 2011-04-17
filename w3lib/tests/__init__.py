from unittest import TestSuite, TestLoader, main
from doctest import DocTestSuite

UNIT_TESTS = [
    'w3lib.tests.test_html',
    'w3lib.tests.test_url',
    'w3lib.tests.test_http',
]

DOC_TESTS = [
    'w3lib.http',
]

def suite():
    suite = TestSuite()
    for m in UNIT_TESTS:
        suite.addTests(TestLoader().loadTestsFromName(m))
    for m in DOC_TESTS:
        suite.addTest(DocTestSuite(__import__(m, {}, {}, [''])))
    return suite
