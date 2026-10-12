"""CPF and CNPJ: check-digit validation and formatting.

CNPJ accepts the alphanumeric format the Receita Federal introduced in 2026 (letters in the first
12 positions, value of each character = ASCII code - 48), which also covers the numeric format.
"""

from __future__ import annotations

import re

_CNPJ_BODY = re.compile(r"^[0-9A-Z]{12}\d{2}$")


def clean(value: str) -> str:
    """Drop punctuation and spaces, keep digits and letters (uppercase)."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def _mod11(values: list[int], weights: list[int]) -> int:
    rest = sum(v * w for v, w in zip(values, weights, strict=True)) % 11
    return 0 if rest < 2 else 11 - rest


def cpf_is_valid(value: str) -> bool:
    digits = clean(value)
    if not re.fullmatch(r"\d{11}", digits) or digits == digits[0] * 11:
        return False
    nums = [int(d) for d in digits]
    first = _mod11(nums[:9], list(range(10, 1, -1)))
    second = _mod11(nums[:10], list(range(11, 1, -1)))
    return nums[9:] == [first, second]


CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
CNPJ_WEIGHTS_2 = [6, *CNPJ_WEIGHTS_1]


def cnpj_is_valid(value: str) -> bool:
    chars = clean(value)
    if not _CNPJ_BODY.match(chars) or chars == chars[0] * 14:
        return False
    nums = [ord(c) - 48 for c in chars]
    first = _mod11(nums[:12], CNPJ_WEIGHTS_1)
    second = _mod11(nums[:13], CNPJ_WEIGHTS_2)
    return nums[12:] == [first, second]


def kind(value: str) -> str | None:
    """'CPF', 'CNPJ' or None when the number is not a valid one of either."""
    if cpf_is_valid(value):
        return "CPF"
    if cnpj_is_valid(value):
        return "CNPJ"
    return None


def format_document(value: str) -> str:
    """123.456.789-09 or 12.345.678/0001-95; anything invalid is returned as typed."""
    c = clean(value)
    if cpf_is_valid(c):
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
    if cnpj_is_valid(c):
        return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    return value
