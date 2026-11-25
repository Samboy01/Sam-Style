"""Tester för webhooken och signaturkontrollen (IFK4)."""

import base64
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.shopify import verify_webhook

client = TestClient(app)
SECRET = config.SHOPIFY_WEBHOOK_SECRET
URL = "/webhooks/shopify/orders"


def sign(body: bytes, secret: str = SECRET) -> str:
    """Signerar som Shopify gör."""
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


ORDER = json.dumps(
    {"id": 5123456789012, "name": "#1001", "email": "anna@example.com",
     "line_items": [{"sku": "SB-TSH-001", "quantity": 2}]}
).encode()


# --- verify_webhook ---

def test_ratt_signatur_godkanns():
    assert verify_webhook(ORDER, sign(ORDER), SECRET)


def test_fel_signatur_avvisas():
    assert not verify_webhook(ORDER, sign(ORDER, "fel-hemlighet"), SECRET)


def test_andrad_body_avvisas():
    signatur = sign(ORDER)
    manipulerad = ORDER.replace(b'"quantity": 2', b'"quantity": 200')
    assert not verify_webhook(manipulerad, signatur, SECRET)


def test_saknad_signatur_avvisas():
    assert not verify_webhook(ORDER, None, SECRET)


def test_tom_hemlighet_avvisar_allt():
    assert not verify_webhook(ORDER, sign(ORDER, ""), "")


# --- endpointen ---

def post(body: bytes, signature: str | None, topic: str = "orders/paid"):
    headers = {"Content-Type": "application/json", "X-Shopify-Topic": topic}
    if signature is not None:
        headers["X-Shopify-Hmac-Sha256"] = signature
    return client.post(URL, content=body, headers=headers)


def test_giltig_order_tas_emot():
    r = post(ORDER, sign(ORDER))
    assert r.status_code == 200
    assert r.json()["status"] == "mottagen"
    assert r.json()["correlation_id"]


def test_ogiltig_signatur_ger_401():
    assert post(ORDER, sign(ORDER, "fel-hemlighet")).status_code == 401


def test_saknad_signatur_ger_401():
    assert post(ORDER, None).status_code == 401


def test_annat_amne_ignoreras():
    r = post(ORDER, sign(ORDER), topic="orders/create")
    assert r.status_code == 200
    assert r.json()["status"] == "ignorerad"


def test_epost_loggas_inte(caplog):
    """IFK3: kundens e-post får inte hamna i loggen."""
    with caplog.at_level("INFO"):
        post(ORDER, sign(ORDER))
    assert "Order mottagen" in caplog.text
    assert "anna@example.com" not in caplog.text
