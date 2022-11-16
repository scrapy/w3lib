# https://www.rfc-editor.org/rfc/rfc5892.txt

from idna import intranges_contain, valid_contextj
from idna.idnadata import codepoint_classes


def _check_contextj_rules(label: str) -> None:
    for i, code_point in enumerate(label):
        value = ord(code_point)
        if not intranges_contain(value, codepoint_classes["CONTEXTJ"]):
            continue
        if valid_contextj(label, i):
            continue
        raise ValueError(
            f"Joiner U+{value:04X} not allowed at position {i+1} in {label!r}"
        )
