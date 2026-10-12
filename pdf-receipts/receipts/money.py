"""Brazilian currency parsing and formatting."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

CENT = Decimal("0.01")


def parse_brl(text: str | int | float | Decimal) -> Decimal:
    """'R$ 1.234,56', '1234,56', '1234.56' and '1.234' (thousands) -> Decimal('1234.56')."""
    if isinstance(text, Decimal | int):
        return Decimal(text).quantize(CENT)
    if isinstance(text, float):
        return Decimal(str(text)).quantize(CENT)
    s = re.sub(r"[R$\s]", "", text or "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")  # 1.234 is one thousand two hundred and thirty-four reais
    try:
        value = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {text!r}") from None
    if not value.is_finite():
        raise ValueError(f"invalid amount: {text!r}")
    return value.quantize(CENT)


def format_brl(value: Decimal) -> str:
    """Decimal('1234.5') -> 'R$ 1.234,50'."""
    return "R$ " + f"{value.quantize(CENT):,.2f}".translate(str.maketrans(",.", ".,"))
