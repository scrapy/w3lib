import six
collect_ignore = ["scrapy/stats.py"]

if six.PY3:
    for fn in open('w3lib/tests/py3-ignores.txt'):
        if fn.strip():
            collect_ignore.append(fn.strip())
