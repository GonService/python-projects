import pytest

from receipts.web import create_app
from tests.test_receipts import FIELDS, ISSUER


@pytest.fixture
def client():
    app = create_app(ISSUER)
    app.config["TESTING"] = True
    return app.test_client()


def test_form_is_prefilled_with_issuer(client):
    page = client.get("/").get_data(as_text=True)
    assert "Emitir recibo" in page and 'value="Studio Movimento Pilates Ltda"' in page


def test_post_returns_pdf(client):
    res = client.post("/recibo", data={**ISSUER, **FIELDS, "numero": "15"})
    assert res.status_code == 200 and res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF")
    assert res.headers["Content-Disposition"] == 'inline; filename="recibo-15.pdf"'
    download = client.post("/recibo", data={**ISSUER, **FIELDS, "download": "1"})
    assert download.headers["Content-Disposition"].startswith("attachment")


def test_post_with_errors_shows_form(client):
    res = client.post("/recibo", data={**ISSUER, **FIELDS, "documento_pagador": "111.111.111-11", "valor": ""})
    page = res.get_data(as_text=True)
    assert res.status_code == 422
    assert "CPF ou CNPJ inválido" in page and "Valor inválido" in page
    assert 'value="Ana Paula Ribeiro"' in page  # what was typed is kept


def test_api_helpers(client):
    assert client.get("/api/extenso?valor=1.200,50").get_json()["extenso"] == (
        "um mil e duzentos reais e cinquenta centavos"
    )
    assert client.get("/api/extenso?valor=xyz").status_code == 400
    assert client.get("/api/documento?numero=54.323.194/0001-95").get_json() == {
        "numero": "54.323.194/0001-95",
        "tipo": "CNPJ",
        "valido": True,
    }
    assert client.get("/healthz").get_json() == {"status": "ok"}
