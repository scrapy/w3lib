# -*- coding: utf-8 -*-
"""
Which string type to use?
=========================

1. Variable is an URL ==> use ``str``
2. Variable is binary; unicode is not accepted ==> use ``bytes``
3. Variable is text, and it can be only unicode in Python 2 ==> use
   ``six.text_type``  (or typing.Text??)
4. Variable is text, but it can be ascii or utf8-encoded str
   in Python 2 ==> use w3lib._types.String
5. Variable can be either bytes or unicode both in Python 2
   and Python 3 ==> use typing.AnyStr
6. Variable should be str (==bytes) in Python 2
   and str (==unicode) in Python 3 ==> use ``str``.

"""
from __future__ import absolute_import
from typing import Union
import six

if six.PY2:
    String = Union[bytes, unicode]
else:
    String = str
