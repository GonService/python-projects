import io

import pytest

from app import brl, create_app
from tests.test_report import CSV


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def upload(client, url, data=CSV, name="sales.csv"):
    return client.post(url, data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")


def test_home_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Create report" in res.data


def test_html_report_and_excel_download(client):
    res = upload(client, "/report")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "R$ 363,50" in html
    assert "Grinder" in html
    key = html.split("/report/")[1].split(".xlsx")[0]
    xlsx = client.get(f"/report/{key}.xlsx")
    assert xlsx.status_code == 200
    assert xlsx.headers["Content-Disposition"].startswith("attachment")
    assert client.get("/report/unknown.xlsx").status_code == 404


def test_html_error_is_shown_on_the_form(client):
    res = upload(client, "/report", b"a,b\n1,2\n")
    assert res.status_code == 400
    assert b"Missing columns" in res.data


def test_json_api(client):
    res = upload(client, "/api/report")
    assert res.status_code == 200
    body = res.get_json()
    assert body["revenue"] == "363.50"
    assert body["period"] == {"from": "2026-07-01", "to": "2026-08-02"}
    assert body["top_products"][0]["product"] == "Grinder"


def test_json_api_errors(client):
    assert client.post("/api/report").status_code == 400
    res = upload(client, "/api/report", b"x", "file.txt")
    assert res.status_code == 400
    assert "csv" in res.get_json()["error"]


def test_upload_limit(client):
    big = b"0" * (6 * 1024 * 1024)
    res = upload(client, "/api/report", big)
    assert res.status_code == 413


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_brl_format():
    assert brl(1234.5) == "R$ 1.234,50"
    assert brl(0) == "R$ 0,00"
