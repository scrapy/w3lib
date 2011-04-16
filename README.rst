=====
w3lib
=====

Overview
========

This is a Python library of web-related functions, such as:

* remove comments, or tags from HTML snippets
* extract base url from HTML snippets
* translate entites on HTML strings
* encoding mulitpart/form-data
* convert raw HTTP headers to dicts and vice-versa
* construct HTTP auth header
* RFC-compliant url joining
* sanitize urls (like browsers do)
* extract arguments from urls

Modules
=======

The w3lib package consists of four modules:

* ``w3lib.url`` - functions for working with URLs
* ``w3lib.html`` - functions for working with HTML
* ``w3lib.http`` - functions for working with HTTP
* ``w3lib.form`` - functions for working with web forms

Requirements
============

* Python 2.5, 2.6 or 2.7

Install
=======

``pip install w3lib``

Documentation
=============

For more information, see the code and tests. The functions are all documented
with docstrings.

History
=======

The code of w3lib was originally part of the `Scrapy framework`_ but was later
stripped out of Scrapy, with the aim of make it more reusable and to provide a
useful library of web functions without depending on Scrapy.

.. _Scrapy framework: http://scrapy.org
