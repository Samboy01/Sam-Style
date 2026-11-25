"""Tester för workerns beslut: klar eller felkö."""

import json

import httpx

from app.worker import handle_order
from test_mapping import SHOPIFY_ORDER

BODY = json.dumps(SHOPIFY_ORDER).encode()


def fake_erp(status_code: int, payload: dict):
    def create_order(erp_order):
        create_order.sent = erp_order
        return httpx.Response(status_code, json=payload)
    return create_order


def test_skapad_i_erp_ar_klar():
    erp = fake_erp(201, {"id": 42})
    outcome = handle_order(BODY, erp)
    assert outcome.ok and outcome.erp_order_id == 42
    assert erp.sent["external_order_id"] == "5123456789012"


def test_dubblett_i_erp_raknas_som_klar():
    assert handle_order(BODY, fake_erp(409, {"detail": "Ordern finns redan"})).ok


def test_okant_artikelnummer_till_felkon():
    outcome = handle_order(BODY, fake_erp(422, {"detail": "Okänt artikelnummer: SB-XXX-999"}))
    assert not outcome.ok
    assert outcome.reason == "ERP svarade 422: Okänt artikelnummer: SB-XXX-999"


def test_erp_nere_till_felkon():
    outcome = handle_order(BODY, fake_erp(503, {"detail": "nere"}))
    assert not outcome.ok and "503" in outcome.reason


def test_timeout_till_felkon():
    def timeout(erp_order):
        raise httpx.ReadTimeout("för långsamt")
    outcome = handle_order(BODY, timeout)
    assert not outcome.ok and outcome.reason == "ERP svarar inte: ReadTimeout"


def test_mappningsfel_skickas_aldrig_till_erp():
    order = dict(SHOPIFY_ORDER, currency="EUR")
    erp = fake_erp(201, {"id": 1})
    outcome = handle_order(json.dumps(order).encode(), erp)
    assert outcome.reason == "Valuta stöds inte: EUR"
    assert not hasattr(erp, "sent")


def test_ogiltig_json_till_felkon():
    assert not handle_order(b"inte json", fake_erp(201, {})).ok
