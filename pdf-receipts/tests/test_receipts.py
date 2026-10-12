from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from receipts.batch import read_csv
from receipts.cli import main
from receipts.model import ReceiptError, build
from receipts.pdf import render

SAMPLE = Path(__file__).parent.parent / "sample" / "recibos.csv"
ISSUER = {"emitente": "Studio Movimento Pilates Ltda", "documento_emitente": "54323194000195", "cidade": "Porto Alegre"}
FIELDS = {"pagador": "Ana Paula Ribeiro", "documento_pagador": "52601815906", "valor": "1.200,50", "referente": "plano"}


def test_build_receipt():
    r = build({**FIELDS, "data": "05/10/2026", "numero": "7"}, ISSUER)
    assert r.amount == Decimal("1200.50") and r.amount_brl == "R$ 1.200,50"
    assert r.amount_words == "um mil e duzentos reais e cinquenta centavos"
    assert r.payer_document == "526.018.159-06" and r.issuer_document == "54.323.194/0001-95"
    assert r.date_long == "5 de outubro de 2026"
    assert r.filename == "recibo-7.pdf"


def test_build_defaults_number_to_date():
    r = build(FIELDS, ISSUER, today=date(2026, 3, 1))
    assert r.issued_on == date(2026, 3, 1) and r.number == "20260301"


def test_build_collects_every_error():
    with pytest.raises(ReceiptError) as info:
        build({"pagador": "A", "documento_pagador": "123.456.789-00", "valor": "abc", "data": "31/02/2026"})
    assert set(info.value.errors) == {
        "pagador",
        "documento_pagador",
        "valor",
        "referente",
        "emitente",
        "documento_emitente",
        "cidade",
        "data",
    }


def test_zero_amount_is_rejected():
    with pytest.raises(ReceiptError) as info:
        build({**FIELDS, "valor": "0,00"}, ISSUER)
    assert "valor" in info.value.errors


def test_pdf_contents():
    receipts = [build({**FIELDS, "numero": "A1"}, ISSUER), build({**FIELDS, "numero": "A2"}, ISSUER)]
    pdf = render(receipts, compress=False)
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 2
    assert b"RECIBO" in pdf and b"1.200,50" in pdf and b"cinquenta centavos" in pdf
    assert b"Recebemos de" in pdf and b"526.018.159-06" in pdf
    assert render(receipts[:1]) != render(receipts[:1], compress=False)


def test_pdf_needs_receipts():
    with pytest.raises(ValueError):
        render([])


def test_sample_csv_is_valid():
    result = read_csv(SAMPLE.read_text(encoding="utf-8"), ISSUER)
    assert result.errors == []
    assert len(result.receipts) == 6
    assert sum(r.amount for r in result.receipts) == Decimal("7006.51")


def test_csv_with_commas_aliases_and_bad_rows():
    text = (
        "Nº,Cliente,CPF,Valor,Descrição\n"
        '1,Bruno Alves,083.016.613-05,"1.000,00",consultoria\n'
        '2,Carla Dias,083.016.613-99,"50,00",aula\n'
        "\n"
        "3,Diego Rocha,,abc,aula\n"
    )
    result = read_csv(text, ISSUER)
    assert [r.payer for r in result.receipts] == ["Bruno Alves"]
    assert [line for line, _ in result.errors] == [3, 5]
    assert "CPF ou CNPJ inválido" in result.errors[0][1]


def test_csv_missing_columns():
    result = read_csv("nome;telefone\nAna;123\n")
    assert result.receipts == [] and "colunas obrigatórias" in result.errors[0][1]


def test_cli_batch(tmp_path, capsys):
    args = ["batch", str(SAMPLE), "--out", str(tmp_path), "--issuer", ISSUER["emitente"]]
    args += ["--issuer-document", ISSUER["documento_emitente"], "--city", "Porto Alegre"]
    assert main(args) == 0
    assert len(list(tmp_path.glob("recibo-*.pdf"))) == 6
    assert "total R$ 7.006,51" in capsys.readouterr().out

    assert main([*args, "--single", "todos.pdf"]) == 0
    assert (tmp_path / "todos.pdf").read_bytes().startswith(b"%PDF")


def test_cli_batch_without_issuer_fails(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ISSUER_NAME", raising=False)
    monkeypatch.delenv("ISSUER_DOCUMENT", raising=False)
    monkeypatch.delenv("ISSUER_CITY", raising=False)
    assert main(["batch", str(SAMPLE), "--out", str(tmp_path)]) == 1
    assert "Informe quem recebeu" in capsys.readouterr().err


def test_cli_extenso(capsys):
    assert main(["extenso", "R$ 2.500.000,00"]) == 0
    assert capsys.readouterr().out.strip() == "dois milhões e quinhentos mil reais"
