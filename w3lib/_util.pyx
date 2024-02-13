import cython

from typing import Union


class _PercentEncodeSet:
    """Set of code points that require percent-encoding.

    The set is comprised of *code_points* and any code point greater than
    *greater_than*.

    If *exclude* is ``True``, *code_points* is interpreted as a string of code
    points *not* to percent-encode, i.e. all other code points lower or equal
    to *greater_than* must be percent-encoded.

    *greater_than* is 0x7F by default, meaning all non-ASCII characters are
    included.
    """

    def __init__(
        self,
        code_points: str,
        *,
        greater_than: Union[int, str] = "\x7f",
        exclude: bool = False,
    ):
        if isinstance(greater_than, str):
            greater_than = ord(greater_than)
        self._greater_than = greater_than
        if exclude:
            code_points = "".join(
                chr(value)
                for value in range(self._greater_than + 1)
                if chr(value) not in code_points
            )
        self._code_points = code_points

    def __contains__(self, code_point: cython.Py_UCS4) -> bool:
        return code_point in self._code_points or ord(code_point) > self._greater_than

    def __add__(self, code_points: str) -> "_PercentEncodeSet":
        return _PercentEncodeSet(
            self._code_points + code_points,
            greater_than=self._greater_than,
        )

    def __sub__(self, code_points: str) -> "_PercentEncodeSet":
        new_code_points = self._code_points
        for code_point in code_points:
            new_code_points = new_code_points.replace(code_point, "")
        return _PercentEncodeSet(
            new_code_points,
            greater_than=self._greater_than,
        )

    def __or__(self, other: "_PercentEncodeSet") -> "_PercentEncodeSet":
        greater_than = min(self._greater_than, other._greater_than)
        code_points = "".join(set(self._code_points) | set(other._code_points))
        return _PercentEncodeSet(
            code_points,
            greater_than=greater_than,
        )

    def __and__(self, other: "_PercentEncodeSet") -> "_PercentEncodeSet":
        greater_than = max(self._greater_than, other._greater_than)
        code_points = "".join(set(self._code_points) & set(other._code_points))
        return _PercentEncodeSet(
            code_points,
            greater_than=greater_than,
        )

    def __repr__(self) -> str:
        cp = "".join(sorted(tuple(self._code_points), key=ord))
        gt = chr(self._greater_than)
        return f"_PercentEncodeSet({cp!r}, greater_than={gt!r})"
