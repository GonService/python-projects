from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

NOW = datetime(2026, 3, 2, 10, 15)  # Monday morning
TUESDAY = "2026-03-03"
ADMIN = {"Authorization": "Bearer s3cret"}


@pytest.fixture
def client():
    settings = Settings(database_url="sqlite://", admin_token="s3cret", seed_demo=True)
    with TestClient(create_app(settings, now=lambda: NOW)) as c:
        yield c


def book(client, starts_at, service_id=3, **extra):
    body = {"service_id": service_id, "starts_at": starts_at, "customer_name": "Beatriz Almeida"}
    body |= {"customer_phone": "(51) 99123-4567"} | extra
    return client.post("/api/bookings", json=body)


def slots(client, day, service_id=3):
    res = client.get(f"/api/services/{service_id}/slots", params={"date": day})
    assert res.status_code == 200
    return [s[11:16] for s in res.json()["slots"]]


def test_services_are_listed(client):
    names = [s["name"] for s in client.get("/api/services").json()]
    assert "Avaliação postural" in names and len(names) == 4


def test_seeded_bookings_are_not_offered(client):
    free = slots(client, TUESDAY)  # demo data books Tuesday 09:00-09:50 and 10:00-10:50
    assert "08:30" in free
    assert "09:00" not in free and "10:00" not in free and "10:30" not in free and "11:00" in free


def test_past_slots_are_hidden_today(client):
    free = slots(client, "2026-03-02")
    assert free[0] == "10:30"


def test_closed_day_and_far_future_have_no_slots(client):
    assert slots(client, "2026-03-08") == []  # Sunday
    assert slots(client, "2026-06-01") == []  # beyond the 30-day horizon


def test_create_get_and_cancel_booking(client):
    res = book(client, f"{TUESDAY}T11:00", customer_email="bia@example.com")
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["service"] == "Avaliação postural" and data["ends_at"].endswith("11:30:00")
    assert "11:00" not in slots(client, TUESDAY)

    code = data["code"]
    assert client.get(f"/api/bookings/{code}").json()["status"] == "confirmed"
    assert client.post(f"/api/bookings/{code}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/bookings/{code}/cancel").status_code == 409
    assert "11:00" in slots(client, TUESDAY)


def test_double_booking_is_rejected(client):
    assert book(client, f"{TUESDAY}T15:30").status_code == 201
    assert book(client, f"{TUESDAY}T15:30", service_id=1).status_code == 409
    # a 50-minute service starting at 15:00 would run into the 15:30 booking
    assert book(client, f"{TUESDAY}T15:00", service_id=1).status_code == 409
    assert book(client, f"{TUESDAY}T16:00").status_code == 201  # back-to-back is fine


def test_rejects_past_closed_and_misaligned_times(client):
    assert book(client, "2026-03-02T09:00").status_code == 409  # already passed
    assert book(client, f"{TUESDAY}T12:30").status_code == 422  # lunch break
    assert book(client, f"{TUESDAY}T11:10").status_code == 422  # not on the 30-minute grid
    assert book(client, f"{TUESDAY}T11:00", service_id=99).status_code == 404


def test_validates_customer_data(client):
    assert book(client, f"{TUESDAY}T11:00", customer_phone="123").status_code == 422
    assert book(client, f"{TUESDAY}T11:00", customer_email="not-an-email").status_code == 422
    assert book(client, f"{TUESDAY}T11:00", customer_name="Al").status_code == 422


def test_admin_requires_token(client):
    assert client.get("/api/admin/bookings").status_code == 401
    assert client.get("/api/admin/bookings", headers={"Authorization": "Bearer wrong"}).status_code == 401
    res = client.get("/api/admin/bookings", headers=ADMIN, params={"date": TUESDAY})
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 4 and rows[0]["customer_phone"].isdigit()


def test_admin_disabled_without_token():
    app = create_app(Settings(database_url="sqlite://", admin_token=""), now=lambda: NOW)
    with TestClient(app) as c:
        assert c.get("/api/admin/bookings", headers=ADMIN).status_code == 503


def test_admin_cancel_and_status_filter(client):
    code = book(client, f"{TUESDAY}T11:00").json()["code"]
    assert client.post(f"/api/admin/bookings/{code}/cancel", headers=ADMIN).json()["status"] == "cancelled"
    cancelled = client.get("/api/admin/bookings", headers=ADMIN, params={"status": "cancelled"}).json()
    assert [b["code"] for b in cancelled] == [code]


def test_html_booking_flow(client):
    page = client.get("/", params={"service": 3, "date": TUESDAY})
    assert page.status_code == 200
    assert "Avaliação postural" in page.text and 'value="2026-03-03T11:00"' in page.text

    form = {"service_id": "3", "starts_at": f"{TUESDAY}T11:00", "name": "Lucas Ferreira", "phone": "51 98888-7777"}
    res = client.post("/book", data=form, follow_redirects=False)
    assert res.status_code == 303
    detail = client.get(res.headers["location"])
    assert "Agendamento confirmado" in detail.text and "11:00 às 11:30" in detail.text

    again = client.post("/book", data=form)
    assert again.status_code == 409 and "reservado por outra pessoa" in again.text

    client.post(res.headers["location"] + "/cancel")
    assert "Agendamento cancelado" in client.get(res.headers["location"]).text


def test_html_form_without_slot_shows_error(client):
    res = client.post("/book", data={"service_id": "3", "name": "Lucas", "phone": "51988887777"})
    assert res.status_code == 422 and "Escolha um horário" in res.text


def test_openapi_and_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/bookings" in paths and "/" not in paths
