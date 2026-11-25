"""Integrationstjänst: tar emot ordrar från webshoppen och för dem vidare till affärssystemet."""

import json
import logging
import uuid

from fastapi import FastAPI, Header, HTTPException, Request, status

from . import config
from .broker import publish_order
from .shopify import verify_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
log = logging.getLogger("integration")

app = FastAPI(
    title="Integrationstjänst",
    description="Tar emot ordrar från Shopify och för dem vidare till mini-ERP:t.",
    version="0.1.0",
)

HANDLED_TOPIC = "orders/paid"


@app.get("/health", tags=["Drift"])
def health():
    return {"status": "ok"}


@app.post("/webhooks/shopify/orders", tags=["Webhooks"])
async def shopify_order_webhook(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_topic: str | None = Header(default=None),
    x_shopify_webhook_id: str | None = Header(default=None),
):
    """Tar emot en order från Shopify (flöde 1, steg 1–4 i integrationsspecifikationen)."""
    raw_body = await request.body()

    # Steg 2: verifiera signaturen innan vi gör något annat med innehållet.
    if not verify_webhook(raw_body, x_shopify_hmac_sha256, config.SHOPIFY_WEBHOOK_SECRET):
        log.warning("Webhook avvisad: ogiltig signatur (webhook_id=%s)", x_shopify_webhook_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ogiltig signatur")

    correlation_id = str(uuid.uuid4())

    if x_shopify_topic != HANDLED_TOPIC:
        log.info("Webhook ignorerad: ämne %s (correlation_id=%s)", x_shopify_topic, correlation_id)
        return {"status": "ignorerad", "correlation_id": correlation_id}

    try:
        order = json.loads(raw_body)
    except ValueError:
        log.warning("Webhook avvisad: ogiltig JSON (correlation_id=%s)", correlation_id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ogiltig JSON")

    # Bara ID:n loggas, aldrig e-post, namn eller adress (IFK3).
    log.info(
        "Order mottagen: order_id=%s name=%s rader=%d webhook_id=%s correlation_id=%s",
        order.get("id"),
        order.get("name"),
        len(order.get("line_items", [])),
        x_shopify_webhook_id,
        correlation_id,
    )

    # Steg 3: lägg ordern på kön. Hela Shopify-ordern sparas, så att den kan mappas om
    # och köras om om mappningen behöver rättas.
    # TODO (#12): spara ordern med status "mottagen"
    headers = {
        "correlation_id": correlation_id,
        "shopify_order_id": str(order.get("id")),
        "shopify_webhook_id": x_shopify_webhook_id,
    }
    try:
        publish_order(raw_body, headers)
    except Exception:
        # Kön är inte nåbar. Svara 503 så att Shopify skickar ordern igen senare (IFK1).
        log.exception("Kunde inte lägga ordern på kön (correlation_id=%s)", correlation_id)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Kön är inte tillgänglig")

    # Steg 4: svara direkt. Själva överföringen görs av workern.
    return {"status": "mottagen", "correlation_id": correlation_id}
