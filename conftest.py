import six
collect_ignore = []

if six.PY3:
    for fn in open('tests/py3-ignores.txt'):
        if fn.strip():
            collect_ignore.append(fn.strip())
