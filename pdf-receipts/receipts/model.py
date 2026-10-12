"""The receipt itself and how it is built (and validated) from form fields or CSV rows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from .documents import format_document, kind
from .extenso import MAX, reais_por_extenso
from .money import format_brl, parse_brl

MONTHS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]  # fmt: skip
FIELDS = (
    "numero", "data", "pagador", "documento_pagador", "valor", "referente",
    "forma_pagamento", "emitente", "documento_emitente", "cidade",
)  # fmt: skip


@dataclass(frozen=True)
class Receipt:
    number: str
    issued_on: date
    payer: str
    payer_document: str
    amount: Decimal
    description: str
    issuer: str
    issuer_document: str
    city: str
    payment_method: str = ""

    @property
    def amount_brl(self) -> str:
        return format_brl(self.amount)

    @property
    def amount_words(self) -> str:
        return reais_por_extenso(self.amount)

    @property
    def date_long(self) -> str:
        d = self.issued_on
        return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"

    @property
    def filename(self) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in self.number)
        return f"recibo-{safe}.pdf"


class ReceiptError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def parse_date(text: str) -> date:
    text = (text or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(text)


def build(fields: Mapping[str, str], defaults: Mapping[str, str] | None = None, today: date | None = None) -> Receipt:
    """Validate the fields (Portuguese names, see FIELDS) and return a Receipt, or raise ReceiptError."""
    values = {k: (fields.get(k) or "").strip() for k in FIELDS}
    for key, value in (defaults or {}).items():
        values[key] = values.get(key) or (value or "").strip()
    errors: dict[str, str] = {}

    for key, label in (("pagador", "Informe quem pagou."), ("referente", "Informe a que se refere o pagamento.")):
        if len(values[key]) < 3:
            errors[key] = label
    if len(values["emitente"]) < 3:
        errors["emitente"] = "Informe quem recebeu (emitente)."
    if not values["cidade"]:
        errors["cidade"] = "Informe a cidade."

    for key in ("documento_pagador", "documento_emitente"):
        if values[key] and kind(values[key]) is None:
            errors[key] = "CPF ou CNPJ inválido (confira os dígitos verificadores)."
    if not values["documento_emitente"] and "documento_emitente" not in errors:
        errors["documento_emitente"] = "Informe o CPF ou CNPJ de quem recebeu."

    amount = Decimal(0)
    try:
        amount = parse_brl(values["valor"])
        if amount <= 0 or amount > MAX:
            errors["valor"] = "O valor deve ser maior que zero."
    except ValueError:
        errors["valor"] = "Valor inválido. Use o formato 1.234,56."

    issued_on = today or date.today()
    if values["data"]:
        try:
            issued_on = parse_date(values["data"])
        except ValueError:
            errors["data"] = "Data inválida. Use dd/mm/aaaa."

    if errors:
        raise ReceiptError(errors)
    return Receipt(
        number=values["numero"] or issued_on.strftime("%Y%m%d"),
        issued_on=issued_on,
        payer=values["pagador"],
        payer_document=format_document(values["documento_pagador"]),
        amount=amount,
        description=values["referente"],
        issuer=values["emitente"],
        issuer_document=format_document(values["documento_emitente"]),
        city=values["cidade"],
        payment_method=values["forma_pagamento"],
    )
