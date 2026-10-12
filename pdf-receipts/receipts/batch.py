"""Read receipts from a CSV file (comma or semicolon, UTF-8 or Excel's Latin-1)."""

from __future__ import annotations

import csv
import io
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from .model import FIELDS, Receipt, ReceiptError, build

# Accept a few common header spellings and English names.
ALIASES = {
    "numero": "numero", "n": "numero", "number": "numero", "recibo": "numero",
    "data": "data", "date": "data",
    "pagador": "pagador", "cliente": "pagador", "nome": "pagador", "payer": "pagador",
    "documento_pagador": "documento_pagador", "cpf_cnpj": "documento_pagador", "cpf": "documento_pagador",
    "cnpj": "documento_pagador", "documento": "documento_pagador", "payer_document": "documento_pagador",
    "valor": "valor", "amount": "valor",
    "referente": "referente", "referente_a": "referente", "descricao": "referente", "description": "referente",
    "forma_pagamento": "forma_pagamento", "forma_de_pagamento": "forma_pagamento", "pagamento": "forma_pagamento",
    "emitente": "emitente", "documento_emitente": "documento_emitente", "cidade": "cidade", "city": "cidade",
}  # fmt: skip


@dataclass
class BatchResult:
    receipts: list[Receipt] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)  # (line number, message)


def _key(header: str) -> str:
    text = unicodedata.normalize("NFKD", header.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace(" ", "_").replace("-", "_").replace("º", "").replace("°", "")
    return ALIASES.get(text, text)


def decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def read_csv(text: str, defaults: Mapping[str, str] | None = None, today: date | None = None) -> BatchResult:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    result = BatchResult()
    try:
        header = [_key(h) for h in next(reader)]
    except StopIteration:
        result.errors.append((1, "arquivo vazio"))
        return result
    missing = {"pagador", "valor", "referente"} - set(header)
    if missing:
        result.errors.append((1, "colunas obrigatórias ausentes: " + ", ".join(sorted(missing))))
        return result
    for line, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        fields = {h: v for h, v in zip(header, row, strict=False) if h in FIELDS}
        try:
            result.receipts.append(build(fields, defaults, today))
        except ReceiptError as exc:
            result.errors.append((line, "; ".join(exc.errors.values())))
    return result
