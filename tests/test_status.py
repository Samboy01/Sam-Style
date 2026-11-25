"""Tester för statustabellen (FK7) och dubblettskyddet i webhooken (IFK2)."""

import pytest
from fastapi.testclient import TestClient

from app import main, status
from app.db import SessionLocal
from test_webhook import ORDER, post, sign

client = TestClient(main.app)
ADMIN = {"X-Admin-Key": "test-admin"}


@pytest.fixture
def queue(monkeypatch):
    published = []
    monkeypatch.setattr(main, "publish_order", lambda body, headers: published.append(headers))
    return published


def current(order_id="5123456789012"):
    with SessionLocal() as db:
        return status.get(db, order_id)


def test_ny_order_far_status_mottagen(queue):
    post(ORDER, sign(ORDER))
    row = current()
    assert row.status == "mottagen"
    assert row.shopify_order_no == "#1001"
    assert row.correlation_id == queue[0]["correlation_id"]


def test_dubblett_laggs_inte_pa_kon_igen(queue):
    first = post(ORDER, sign(ORDER)).json()
    second = post(ORDER, sign(ORDER)).json()
    assert second["status"] == "dubblett"
    assert second["correlation_id"] == first["correlation_id"]
    assert len(queue) == 1


def test_kon_nere_registrerar_inte_ordern(monkeypatch):
    """Om kön är nere får ordern inte se ut som mottagen – då skulle Shopifys nya försök
    behandlas som en dubblett och ordern försvinna."""
    def broken(body, headers):
        raise ConnectionError("RabbitMQ nere")
    monkeypatch.setattr(main, "publish_order", broken)
    assert post(ORDER, sign(ORDER)).status_code == 503
    assert current() is None


def test_hela_livscykeln_till_klar():
    with SessionLocal() as db:
        assert status.register_received(db, "1", "#1", "corr-1")
        db.commit()
        status.mark_sent(db, "1", "#1", "corr-1")
        status.mark_done(db, "1", erp_order_id=42)
    row = current("1")
    assert (row.status, row.attempts, row.erp_order_id, row.last_error) == ("klar", 1, 42, None)


def test_worker_skapar_rad_om_den_saknas():
    # Själva kapplöpningen (worker före webhookens commit) kräver PostgreSQL och
    # testas i integrationstesterna med många ordrar samtidigt.
    with SessionLocal() as db:
        status.mark_sent(db, "4", "#4", "corr-4")
    assert current("4").status == "skickad"


def test_fel_sparar_orsak():
    with SessionLocal() as db:
        status.mark_sent(db, "2", "#2", "corr-2")  # även utan registrering
        status.mark_failed(db, "2", "Okänt artikelnummer: SB-XXX-999")
    row = current("2")
    assert row.status == "fel"
    assert row.last_error == "Okänt artikelnummer: SB-XXX-999"


def test_admin_kraver_nyckel(queue):
    assert client.get("/admin/orders").status_code == 401
    assert client.get("/admin/orders", headers={"X-Admin-Key": "fel"}).status_code == 401


def test_admin_visar_status(queue):
    post(ORDER, sign(ORDER))
    r = client.get("/admin/orders/5123456789012", headers=ADMIN)
    assert r.status_code == 200 and r.json()["status"] == "mottagen"
    assert client.get("/admin/orders?status_filter=fel", headers=ADMIN).json() == []
    assert len(client.get("/admin/orders?status_filter=mottagen", headers=ADMIN).json()) == 1
    assert client.get("/admin/orders/finns-inte", headers=ADMIN).status_code == 404
