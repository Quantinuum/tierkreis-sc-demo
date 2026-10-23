"""Normalize upstream FCIDUMP syntax for the PySCF parser."""

import re


def normalize_fcidump(text: str) -> str:
    text = re.sub(
        r"(\bISYM\s*=\s*\d+)\s+(?=UHF\s*=)", r"\1,", text, flags=re.IGNORECASE
    )
    return re.sub(r"(?<=\d)[dD](?=[+-]\d)", "E", text)
