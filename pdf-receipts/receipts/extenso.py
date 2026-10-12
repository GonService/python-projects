"""Amounts written out in Brazilian Portuguese, as receipts and cheques require.

>>> reais_por_extenso(Decimal("1200.50"))
'um mil e duzentos reais e cinquenta centavos'

"Um mil" (instead of just "mil") is the usual choice on receipts: it makes it harder to add a digit
in front of the written amount.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

UNITS = [
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
    "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove",
]  # fmt: skip
TENS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
HUNDREDS = [
    "", "cento", "duzentos", "trezentos", "quatrocentos",
    "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos",
]  # fmt: skip
# (singular, plural) for each group of three digits above the units group.
SCALES = [("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões"), ("trilhão", "trilhões")]
MAX = 10**15 - 1


def _below_thousand(n: int) -> str:
    if n == 100:
        return "cem"
    hundreds, rest = divmod(n, 100)
    parts = [HUNDREDS[hundreds]] if hundreds else []
    if rest:
        if rest < 20:
            parts.append(UNITS[rest])
        else:
            tens, units = divmod(rest, 10)
            parts.append(TENS[tens] + (f" e {UNITS[units]}" if units else ""))
    return " e ".join(parts)


def number_words(n: int) -> str:
    """Cardinal number in words: 1250 -> 'um mil duzentos e cinquenta'."""
    if n < 0 or n > MAX:
        raise ValueError(f"out of range: {n}")
    if n == 0:
        return "zero"
    groups = []  # least significant first
    while n:
        n, group = divmod(n, 1000)
        groups.append(group)
    words: list[tuple[int, str]] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            continue
        text = _below_thousand(group)
        if index:
            singular, plural = SCALES[index - 1]
            text += " " + (singular if group == 1 else plural)
        words.append((group, text))
    if len(words) == 1:
        return words[0][1]
    # "e" joins the last group when it is below 100 or a round hundred: "um mil e duzentos",
    # "dois mil e cinco", but "um mil duzentos e cinquenta".
    *head, (last_value, last_text) = words
    joiner = " e " if last_value < 100 or last_value % 100 == 0 else " "
    return " ".join(text for _, text in head) + joiner + last_text


def reais_por_extenso(value: Decimal | int | float | str) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < 0:
        raise ValueError("negative amount")
    reais = int(amount)
    centavos = int((amount - reais) * 100)
    parts = []
    if reais or not centavos:
        words = number_words(reais)
        # "um milhão de reais", but "um milhão e cem mil reais"
        connector = " de " if reais >= 1_000_000 and reais % 1_000_000 == 0 else " "
        parts.append(words + connector + ("real" if reais == 1 else "reais"))
    if centavos:
        parts.append(number_words(centavos) + (" centavo" if centavos == 1 else " centavos"))
    return " e ".join(parts)
