from decimal import Decimal

import pytest

from receipts.documents import cnpj_is_valid, cpf_is_valid, format_document, kind
from receipts.money import format_brl, parse_brl


@pytest.mark.parametrize("cpf", ["526.018.159-06", "52601815906", "083.016.613-05", " 186 091 390 34 "])
def test_valid_cpf(cpf):
    assert cpf_is_valid(cpf)


@pytest.mark.parametrize("cpf", ["526.018.159-07", "526.018.159-60", "111.111.111-11", "1234567890", "", "abc"])
def test_invalid_cpf(cpf):
    assert not cpf_is_valid(cpf)


@pytest.mark.parametrize("cnpj", ["54.323.194/0001-95", "87574911000100", "12.ABC.345/01DE-35", "12abc34501de35"])
def test_valid_cnpj_numeric_and_alphanumeric(cnpj):
    assert cnpj_is_valid(cnpj)


@pytest.mark.parametrize("cnpj", ["54.323.194/0001-96", "00.000.000/0000-00", "12.ABC.345/01DE-36", "5432319400019"])
def test_invalid_cnpj(cnpj):
    assert not cnpj_is_valid(cnpj)


def test_kind_and_format():
    assert kind("52601815906") == "CPF"
    assert kind("54323194000195") == "CNPJ"
    assert kind("123") is None
    assert format_document("52601815906") == "526.018.159-06"
    assert format_document("54323194000195") == "54.323.194/0001-95"
    assert format_document("12abc34501de35") == "12.ABC.345/01DE-35"
    assert format_document("999") == "999"


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("R$ 1.234,56", "1234.56"),
        ("1234,5", "1234.50"),
        ("1234.56", "1234.56"),
        ("1.234", "1234.00"),
        ("1.234.567", "1234567.00"),
        ("0,01", "0.01"),
        (" 95 ", "95.00"),
    ],
)
def test_parse_brl(text, value):
    assert parse_brl(text) == Decimal(value)


@pytest.mark.parametrize("bad", ["", "abc", "1,2,3", "NaN", "inf"])
def test_parse_brl_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_brl(bad)


def test_format_brl():
    assert format_brl(Decimal("1234567.5")) == "R$ 1.234.567,50"
    assert format_brl(Decimal("0.5")) == "R$ 0,50"
