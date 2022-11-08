from ._infra import _ASCII_ALPHANUMERIC
from ._util import _PercentEncodeSet


_RFC3986_UNRESERVED_PERCENT_ENCODE_SET = _PercentEncodeSet(
    _ASCII_ALPHANUMERIC + "-._~",
    exclude=True,
)
_RFC3986_SUB_DELIMS_PERCENT_ENCODE_SET = _PercentEncodeSet(
    "!$&'()*+,;=",
    exclude=True,
)
_RFC3986_USERINFO_PERCENT_ENCODE_SET = (
    _RFC3986_UNRESERVED_PERCENT_ENCODE_SET & _RFC3986_SUB_DELIMS_PERCENT_ENCODE_SET
) - ":"
