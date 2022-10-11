=====
w3lib
=====

.. image:: https://github.com/scrapy/w3lib/actions/workflows/tests.yml/badge.svg
   :target: https://github.com/scrapy/w3lib/actions

.. image:: https://img.shields.io/codecov/c/github/scrapy/w3lib/master.svg
   :target: http://codecov.io/github/scrapy/w3lib?branch=master
   :alt: Coverage report


Overview
========

w3lib is an amazing Python library of web-related functions, such as:

* Remove comments, or tags from HTML snippets
* Extract base url from HTML snippets
* Translate entites on HTML strings
* Convert raw HTTP headers to dicts and vice-versa
* Construct HTTP auth header
* Converting HTML pages to unicode
* Sanitize URLs (like browsers do)
* Extract arguments from URLs

Requirements
============

Python 3.6+ (https://python.org)

Install
=======

``pip install w3lib``

Tests
=====
* pytest is the preferred way to run tests. Just run: pytest from the root directory to execute tests using the default Python interpreter.

* tox could be used to run tests for all supported Python versions. Install it (using ‘pip install tox’) and then run tox from the root directory - tests will be executed for all available Python interpreters.


Documentation
=============

See http://w3lib.readthedocs.org/

License
=======

The w3lib library is licensed under the BSD license. (https://github.com/scrapy/w3lib/blob/master/LICENSE)
