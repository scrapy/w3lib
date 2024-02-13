# https://www.unicode.org/reports/tr46/

import re
import unicodedata
from enum import auto, Enum
from pathlib import Path
from typing import Dict, Match, Optional, Type

from ._rfc5892 import _check_contextj_rules
from idna import check_bidi as _check_bidi


if hasattr(unicodedata, "is_normalized"):
    _is_normalized = unicodedata.is_normalized
else:

    def _is_normalized(form: str, unistr: str) -> bool:
        return unicodedata.normalize(form, unistr) == unistr


class _Status(Enum):
    DISALLOWED = auto()
    DISALLOWED_STD3_MAPPED = auto()
    DISALLOWED_STD3_VALID = auto()
    IGNORED = auto()
    MAPPED = auto()
    DEVIATION = auto()
    VALID = auto()


class _Entry:  # pylint: disable=too-few-public-methods
    @classmethod
    def from_match(cls: Type["_Entry"], match: Match) -> "_Entry":
        if match["status"] == "disallowed":
            status = _Status.DISALLOWED
        elif match["status"] == "disallowed_STD3_mapped":
            status = _Status.DISALLOWED_STD3_MAPPED
        elif match["status"] == "disallowed_STD3_valid":
            status = _Status.DISALLOWED_STD3_VALID
        elif match["status"] == "ignored":
            status = _Status.IGNORED
        elif match["status"] == "mapped":
            status = _Status.MAPPED
        elif match["status"] == "deviation":
            status = _Status.DEVIATION
        elif match["status"] == "valid":
            status = _Status.VALID
        else:
            raise ValueError(
                f"Unknown IDNA mapping table status value found: "
                f"{match['status']!r}"
            )
        if match["mapping"] is None:
            mapping = None
        else:
            mapping = "".join(
                chr(int(value, base=16)) for value in match["mapping"].split(" ")
            )
        return cls(
            mapping=mapping,
            status=status,
        )

    def __init__(self: "_Entry", *, mapping: Optional[str], status: _Status) -> None:
        self.mapping = mapping
        self.status = status


def _load_idna_mapping_table() -> Dict[str, _Entry]:
    file_name = Path(__file__).parent / "idna.txt"
    pattern = r"""(?x)
        ^
        (?:
            (?P<id>[0-9A-F]{4,6})
            |(?P<start>[0-9A-F]{4,6})\.\.(?P<end>[0-9A-F]{4,6})
        )
        \s*;\s*
        (?P<status>
            disallowed(?:_STD3_(?:mapped|valid))?
            |ignored
            |mapped
            |deviation
            |valid
        )
        (?:
            \s*;\s*
            (?P<mapping>
                [0-9A-F]{4,6}
                (\s[0-9A-F]{4,6})*
            )
        )?
    """
    mapping = {}
    with open(file_name, encoding="utf-8") as input:
        for line in input:
            if line.startswith("#") or not line.strip():
                continue
            match = re.search(pattern, line)
            if not match:
                raise ValueError(
                    f"Line {line!r} from {file_name} does not match the "
                    f"expected pattern."
                )
            entry = _Entry.from_match(match)
            if match["id"] is not None:
                code_point = chr(int(match["id"], base=16))
                mapping[code_point] = entry
                continue
            start = int(match["start"], base=16)
            end = int(match["end"], base=16)
            for id in range(start, end + 1):
                code_point = chr(id)
                mapping[code_point] = entry
    return mapping


_IDNA_MAPPING_TABLE = _load_idna_mapping_table()


# https://www.unicode.org/reports/tr46/#Validity_Criteria
def _validate_label(
    label: str,
    *,
    check_hyphens: bool,
    check_joiners: bool,
    check_bidi: bool,
    transitional_processing: bool,
    use_std3_ascii_rules: bool,
) -> None:
    """Validates the *label* domain name label.

    Only set *check_bidi* to ``True`` if the source domain name is a bidi
    domain name, i.e. if any character in it is in the Unicode Character
    Database with Bidi_Class R, AL, or AN.
    """
    if not _is_normalized("NFC", label):
        raise ValueError(
            f"Domain name label {label!r} is not in Unicode Normalization " f"Form NFC."
        )
    length = len(label)
    if check_hyphens:
        if length >= 4 and label[3:4] == "--":
            raise ValueError(
                f"Domain name label {label!r} contains '-' in its 3rd and 4rd "
                f"positions."
            )
        if label.startswith("-"):
            raise ValueError(f"Domain name label {label!r} starts with '-'.")
        if label.endswith("-"):
            raise ValueError(f"Domain name label {label!r} ends with '-'.")
    if "." in label:
        raise ValueError(f"Domain name label {label!r} contains a '.'.")
    if length >= 1 and unicodedata.category(label[0])[0] == "M":
        raise ValueError(
            f"Domain name label {label!r} starts with a character "
            f"({label[0]!r}) in the Mark general category from the Unicode "
            f"Character Database."
        )
    for code_point in set(label):
        entry = _IDNA_MAPPING_TABLE.get(code_point)
        if entry is None:
            raise ValueError(
                f"Domain name label {label!r} contains an unrecognized code "
                f"point: U+{ord(code_point):04X} ({code_point})."
            )
        if not (
            entry.status is _Status.VALID
            or not use_std3_ascii_rules
            and entry.status is _Status.DISALLOWED_STD3_VALID
            or not transitional_processing
            and entry.status is _Status.DEVIATION
        ):
            raise ValueError(
                f"Domain name label {label!r} contains a code point, "
                f"U+{ord(code_point):04X} ({code_point}), which is neither "
                f"valid nor a deviation."
            )
    if check_joiners:
        _check_contextj_rules(label)
    if check_bidi:
        _check_bidi(label)


# https://www.unicode.org/reports/tr46/#Notation
def _is_bidi_domain_name(domain_name: str) -> bool:
    return any(
        unicodedata.bidirectional(code_point) in {"AL", "AN", "R"}
        for code_point in set(domain_name)
    )


# https://www.unicode.org/reports/tr46/#Processing
def _process(
    domain_name: str,
    *,
    use_std3_ascii_rules: bool,
    check_hyphens: bool,
    check_bidi: bool,
    check_joiners: bool,
    transitional_processing: bool,
) -> str:
    for code_point in set(domain_name):
        entry = _IDNA_MAPPING_TABLE.get(code_point)
        if entry is None:
            raise ValueError(
                f"Domain name {domain_name!r} contains an unrecognized code "
                f"point: U+{ord(code_point):04X} ({code_point})."
            )
        if entry.status is _Status.DISALLOWED or (
            use_std3_ascii_rules
            and entry.status
            in (
                _Status.DISALLOWED_STD3_MAPPED,
                _Status.DISALLOWED_STD3_VALID,
            )
        ):
            raise ValueError(
                f"Domain name {domain_name!r} contains disallowed code point "
                f"U+{ord(code_point):04X} ({code_point})."
            )
        if entry.status is _Status.IGNORED:
            domain_name = domain_name.replace(code_point, "")
        elif entry.status is _Status.MAPPED or (
            not use_std3_ascii_rules and entry.status is _Status.DISALLOWED_STD3_MAPPED
        ):
            assert entry.mapping is not None
            domain_name = domain_name.replace(code_point, entry.mapping)
        elif entry.status is _Status.DEVIATION and transitional_processing:
            assert entry.mapping is not None
            domain_name = domain_name.replace(code_point, entry.mapping)
    domain_name = unicodedata.normalize("NFC", domain_name)
    labels = domain_name.split(".")
    check_bidi = check_bidi and _is_bidi_domain_name(domain_name)
    for i, label in enumerate(labels):
        if label.startswith("xn--"):
            new_label = label[4:].encode().decode("punycode")
            _validate_label(
                new_label,
                transitional_processing=False,
                check_hyphens=check_hyphens,
                check_joiners=check_joiners,
                check_bidi=check_bidi,
                use_std3_ascii_rules=use_std3_ascii_rules,
            )
            labels[i] = new_label
        else:
            _validate_label(
                label,
                transitional_processing=transitional_processing,
                check_hyphens=check_hyphens,
                check_joiners=check_joiners,
                check_bidi=check_bidi,
                use_std3_ascii_rules=use_std3_ascii_rules,
            )
    return ".".join(labels)


def _convert_label(label: str) -> str:
    if label.isascii():
        return label
    return f"xn--{label.encode('punycode').decode()}"


# https://www.unicode.org/reports/tr46/#ToASCII
def _to_ascii(
    domain_name: str,
    *,
    check_hyphens: bool,
    check_bidi: bool,
    check_joiners: bool,
    use_std3_ascii_rules: bool,
    transitional_processing: bool,
    verify_dns_length: bool,
) -> str:
    domain_name = _process(
        domain_name,
        transitional_processing=transitional_processing,
        check_hyphens=check_hyphens,
        check_bidi=check_bidi,
        check_joiners=check_joiners,
        use_std3_ascii_rules=use_std3_ascii_rules,
    )
    labels = [_convert_label(label) for label in domain_name.split(".")]
    domain_name = ".".join(labels)
    if verify_dns_length:
        length = len(domain_name.rstrip("."))
        if not 1 <= length <= 253:
            raise ValueError(
                f"The length of domain name {domain_name!r}, excluding the "
                f"root label and its dot, is {length}. It should be between 1 "
                f"and 253. Pass verify_dns_length=False to avoid this check."
            )
        for label in labels:
            length = len(label)
            if not 1 <= length <= 63:
                raise ValueError(
                    f"The length of label {label!r} from domain name "
                    f"{domain_name!r} is {length}. It should be between 1 and "
                    f"63. Pass verify_dns_length=False to avoid this check."
                )
    return domain_name
