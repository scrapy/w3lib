# Contributing to w3lib

## Regular expressions

Regular expressions run on untrusted input, so they must take linear time on any input.

- Check each pattern for backtracking: quantifiers or alternatives that can match the same text in more than one way.
- Check the code that applies the pattern in a loop (`sub()`, `finditer()`, `match()`): an attempt that reads to the end of the text and then consumes only a few characters is quadratic, e.g. a long reading that fails before a shorter alternative matches.
- Time adversarial inputs, e.g. a short unit repeated 1000, 2000 and 4000 times, on your branch and on `master`; about 4× per doubling means quadratic. Add them to the `*_no_catastrophic_backtracking` or `test_linear*` tests.
- Flags change existing tokens, e.g. `re.ASCII` changes `\b` and `\s`.

## Performance

Correctness comes first, but look for a fix that does not slow down the benchmarks in `tests/benchmarks/` (`tox -e benchmark`, CodSpeed in CI), and report any slowdown you could not avoid. Common causes: a Python callback per match in `re.sub()`, and extra passes over the whole text.

## Correctness

- Match browser behavior, citing WHATWG commit snapshot links as in `w3lib/_url.py`.
- Fix every case: other functions sharing the flawed code, and unterminated or malformed input.
- Check open pull requests for overlap.

## Tests

- Keep coverage at 100%, branches included; remove code that becomes unreachable.
- Use `pytest.mark.parametrize`, not loops, with short `ids` for long parameters (long test IDs break Windows jobs).

## Comments

Keep them short, and describe what the code does. History, rationale and rejected alternatives belong in the pull request description. Do not comment lines that read fine on their own.

## Checks

Run `tox -e py`, `tox -e typing`, `tox -e pylint` and `tox -e pre-commit`, and keep the pull request free of conflicts with `master`.
