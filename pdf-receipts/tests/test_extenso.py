from decimal import Decimal

import pytest

from receipts.extenso import number_words, reais_por_extenso


@pytest.mark.parametrize(
    ("value", "words"),
    [
        ("1200.50", "um mil e duzentos reais e cinquenta centavos"),
        ("0.01", "um centavo"),
        ("0.99", "noventa e nove centavos"),
        ("0", "zero reais"),
        ("1", "um real"),
        ("1.01", "um real e um centavo"),
        ("2", "dois reais"),
        ("100", "cem reais"),
        ("101", "cento e um reais"),
        ("115", "cento e quinze reais"),
        ("480", "quatrocentos e oitenta reais"),
        ("1000", "um mil reais"),
        ("1001.01", "um mil e um reais e um centavo"),
        ("1250", "um mil duzentos e cinquenta reais"),
        ("2005", "dois mil e cinco reais"),
        ("3750", "três mil setecentos e cinquenta reais"),
        ("21000", "vinte e um mil reais"),
        ("100000", "cem mil reais"),
        ("999999.99", "novecentos e noventa e nove mil novecentos e noventa e nove reais e noventa e nove centavos"),
        ("1000000", "um milhão de reais"),
        ("2000000", "dois milhões de reais"),
        ("2500000", "dois milhões e quinhentos mil reais"),
        ("1000100", "um milhão e cem reais"),
        ("1000000000", "um bilhão de reais"),
    ],
)
def test_reais_por_extenso(value, words):
    assert reais_por_extenso(Decimal(value)) == words


def test_rounds_to_cents():
    assert reais_por_extenso("10.005") == "dez reais e um centavo"


def test_number_words_teens_and_tens():
    assert [number_words(n) for n in (11, 14, 16, 19, 20, 30, 77)] == [
        "onze",
        "quatorze",
        "dezesseis",
        "dezenove",
        "vinte",
        "trinta",
        "setenta e sete",
    ]


@pytest.mark.parametrize("bad", [-1, 10**15])
def test_out_of_range(bad):
    with pytest.raises(ValueError):
        number_words(bad)
    with pytest.raises(ValueError):
        reais_por_extenso(bad)
