"""Enhetstester för mappningen Shopify → ERP (docs/mappning.md)."""

import copy

import pytest

from app.mapping import MappingError, map_order

# Exemplet från avsnitt 5 i docs/mappning.md
SHOPIFY_ORDER = {
    "id": 5123456789012,
    "name": "#1001",
    "created_at": "2026-11-25T13:03:00Z",
    "currency": "SEK",
    "email": "anna@example.com",
    "customer": {"id": 7012345678901, "email": "anna@example.com", "first_name": "Anna"},
    "total_discounts": "0.00",
    "total_price": "745.00",
    "shipping_lines": [{"price": "49.00"}],
    "line_items": [
        {"sku": "SB-TSH-001", "title": "Basic t-shirt vit", "quantity": 2, "price": "199.00"},
        {"sku": "SB-ACC-001", "title": "Mössa svart", "quantity": 1, "price": "149.00"},
        {"sku": "SB-ACC-001", "title": "Mössa svart", "quantity": 1, "price": "149.00"},
    ],
    "shipping_address": {"address1": "Storgatan 1", "city": "Borås"},
}

EXPECTED_ERP_ORDER = {
    "external_order_id": "5123456789012",
    "external_order_no": "#1001",
    "order_date": "2026-11-25T14:03:00+01:00",
    "currency": "SEK",
    "customer_ref": "SHOP-7012345678901",
    "shipping_amount": "49.00",
    "discount_amount": "0.00",
    "total_amount": "745.00",
    "rows": [
        {"article_no": "SB-TSH-001", "description": "Basic t-shirt vit", "qty": 2, "unit_price": "199.00"},
        {"article_no": "SB-ACC-001", "description": "Mössa svart", "qty": 1, "unit_price": "149.00"},
        {"article_no": "SB-ACC-001", "description": "Mössa svart", "qty": 1, "unit_price": "149.00"},
    ],
}


def order(**changes):
    o = copy.deepcopy(SHOPIFY_ORDER)
    o.update(changes)
    return o


def test_exemplet_i_mappningstabellen():
    assert map_order(SHOPIFY_ORDER) == EXPECTED_ERP_ORDER


def test_inga_personuppgifter_fors_over():
    result = str(map_order(SHOPIFY_ORDER))
    for personuppgift in ("anna@example.com", "Anna", "Storgatan", "Borås"):
        assert personuppgift not in result


def test_sommartid():
    assert map_order(order(created_at="2026-07-01T10:00:00Z"))["order_date"] == "2026-07-01T12:00:00+02:00"


def test_kund_saknas_ger_guest():
    assert map_order(order(customer=None))["customer_ref"] == "GUEST"


def test_ingen_frakt_ger_noll():
    assert map_order(order(shipping_lines=[]))["shipping_amount"] == "0.00"


def test_flera_fraktrader_summeras():
    assert map_order(order(shipping_lines=[{"price": "49.00"}, {"price": "10.5"}]))["shipping_amount"] == "59.50"


def test_mellanslag_i_sku_tas_bort():
    o = order(); o["line_items"][0]["sku"] = "  SB-TSH-001 "
    assert map_order(o)["rows"][0]["article_no"] == "SB-TSH-001"


@pytest.mark.parametrize("changes, reason", [
    ({"id": None}, "Order-ID saknas"),
    ({"currency": "EUR"}, "Valuta stöds inte: EUR"),
    ({"line_items": []}, "Ordern saknar rader"),
    ({"total_price": "abc"}, "Ogiltigt belopp i fält total_price"),
    ({"created_at": "igår"}, "Ogiltigt datum i fält created_at"),
])
def test_valideringsfel_pa_ordern(changes, reason):
    with pytest.raises(MappingError, match=reason):
        map_order(order(**changes))


@pytest.mark.parametrize("row_change, reason", [
    ({"sku": ""}, "Rad 2 saknar artikelnummer"),
    ({"sku": None}, "Rad 2 saknar artikelnummer"),
    ({"quantity": 0}, "Rad 2 har ogiltigt antal"),
    ({"quantity": "två"}, "Rad 2 har ogiltigt antal"),
])
def test_valideringsfel_pa_rad(row_change, reason):
    o = order(); o["line_items"][1].update(row_change)
    with pytest.raises(MappingError, match=reason):
        map_order(o)
