"""Översätter en Shopify-order till en ERP-order enligt docs/mappning.md."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

SWEDISH_TIME = ZoneInfo("Europe/Stockholm")
TWO_DECIMALS = Decimal("0.01")


class MappingError(Exception):
    """Ordern går inte att mappa. Alltid ett permanent fel: ska inte försökas igen."""


def _amount(value, field: str) -> str:
    """Text → belopp med två decimaler, skickat som text (t.ex. "199.00")."""
    try:
        return str(Decimal(str(value)).quantize(TWO_DECIMALS))
    except (InvalidOperation, ValueError, TypeError):
        raise MappingError(f"Ogiltigt belopp i fält {field}")


def map_order(order: dict) -> dict:
    """Shopify-order (webhook orders/paid) → anrop till POST /orders i mini-ERP:t."""
    if not order.get("id"):
        raise MappingError("Order-ID saknas")

    currency = order.get("currency")
    if currency != "SEK":
        raise MappingError(f"Valuta stöds inte: {currency}")

    line_items = order.get("line_items") or []
    if not line_items:
        raise MappingError("Ordern saknar rader")

    rows = []
    for n, item in enumerate(line_items, start=1):
        sku = (item.get("sku") or "").strip()
        if not sku:
            raise MappingError(f"Rad {n} saknar artikelnummer")
        qty = item.get("quantity")
        if not isinstance(qty, int) or qty <= 0:
            raise MappingError(f"Rad {n} har ogiltigt antal")
        rows.append({
            "article_no": sku,
            "description": item.get("title"),
            "qty": qty,
            "unit_price": _amount(item.get("price"), f"line_items[{n}].price"),
        })

    try:
        order_date = datetime.fromisoformat(order["created_at"]).astimezone(SWEDISH_TIME)
    except (KeyError, TypeError, ValueError):
        raise MappingError("Ogiltigt datum i fält created_at")

    customer = order.get("customer") or {}
    customer_ref = f"SHOP-{customer['id']}" if customer.get("id") else "GUEST"

    shipping = sum(
        (Decimal(_amount(line.get("price"), "shipping_lines.price")) for line in order.get("shipping_lines") or []),
        Decimal("0"),
    )

    # Fält som avsiktligt inte förs över (dataminimering, IFK6): email, namn, adresser, telefon, note.
    return {
        "external_order_id": str(order["id"]),
        "external_order_no": order.get("name"),
        "order_date": order_date.isoformat(),
        "currency": currency,
        "customer_ref": customer_ref,
        "shipping_amount": str(shipping.quantize(TWO_DECIMALS)),
        "discount_amount": _amount(order.get("total_discounts", "0"), "total_discounts"),
        "total_amount": _amount(order.get("total_price"), "total_price"),
        "rows": rows,
    }
