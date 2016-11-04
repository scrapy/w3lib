Welcome to w3lib's documentation!
=================================

Overview
========

This is a Python library of web-related functions, such as:

* remove comments, or tags from HTML snippets
* extract base url from HTML snippets
* translate entites on HTML strings
* convert raw HTTP headers to dicts and vice-versa
* construct HTTP auth header
* converting HTML pages to unicode
* sanitize urls (like browsers do)
* extract arguments from urls

The w3lib library is licensed under the BSD license.

Modules
=======

.. toctree::
   :maxdepth: 4

   w3lib

Requirements
============

Python 2.7 or Python 3.3+

Install
=======

``pip install w3lib``


Tests
=====

`nose`_ is the preferred way to run tests. Just run: ``nosetests`` from the
root directory to execute tests using the default Python interpreter.

`tox`_ could be used to run tests for all supported Python versions.
Install it (using 'pip install tox') and then run ``tox`` from
the root directory - tests will be executed for all available
Python interpreters.

.. _tox: http://tox.testrun.org
.. _nose: http://readthedocs.org/docs/nose/en/latest/


Changelog
=========

.. include:: ../NEWS
    :start-line: 3

History
-------

The code of w3lib was originally part of the `Scrapy framework`_ but was later
stripped out of Scrapy, with the aim of make it more reusable and to provide a
useful library of web functions without depending on Scrapy.

.. _Scrapy framework: http://scrapy.org
.. _NEWS file: https://github.com/scrapy/w3lib/blob/master/NEWS


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

