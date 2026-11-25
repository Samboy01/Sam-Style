"""Integrationstjänst: tar emot ordrar från webshoppen och för dem vidare till affärssystemet."""

import json
import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from . import config
from . import status as order_status
from .broker import publish_order
from .db import SessionLocal, create_tables
from .models import OrderStatus
from .shopify import verify_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
log = logging.getLogger("integration")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="Integrationstjänst",
    description="Tar emot ordrar från Shopify och för dem vidare till mini-ERP:t.",
    version="0.2.0",
    lifespan=lifespan,
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

    shopify_order_id = str(order.get("id"))
    # Bara ID:n loggas, aldrig e-post, namn eller adress (IFK3).
    ids = f"order_id={shopify_order_id} name={order.get('name')} webhook_id={x_shopify_webhook_id}"

    try:
        with SessionLocal() as db:
            # Steg 3a: registrera ordern. Finns den redan är det en dubblett (IFK2).
            if not order_status.register_received(db, shopify_order_id, order.get("name"), correlation_id):
                existing = order_status.get(db, shopify_order_id)
                log.info("Dubblett ignorerad: %s correlation_id=%s", ids, existing.correlation_id)
                return {"status": "dubblett", "correlation_id": existing.correlation_id}

            # Steg 3b: lägg ordern på kön. Hela Shopify-ordern sparas, så att den kan
            # mappas om och köras om om mappningen behöver rättas.
            publish_order(raw_body, {
                "correlation_id": correlation_id,
                "shopify_order_id": shopify_order_id,
                "shopify_order_no": order.get("name"),
                "shopify_webhook_id": x_shopify_webhook_id,
            })
            # Sparas först när ordern ligger säkert på kön. Misslyckas kön ångras registreringen,
            # så att ordern inte ser ut som en dubblett när Shopify skickar den igen.
            db.commit()
    except Exception:
        # Kön eller databasen är inte nåbar. Svara 503 så att Shopify skickar igen senare (IFK1).
        log.exception("Kunde inte ta emot ordern: %s correlation_id=%s", ids, correlation_id)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Tillfälligt fel, försök igen")

    log.info("Order mottagen: %s rader=%d correlation_id=%s",
             ids, len(order.get("line_items", [])), correlation_id)

    # Steg 4: svara direkt. Själva överföringen görs av workern.
    return {"status": "mottagen", "correlation_id": correlation_id}


# --- Admin: läsa status (FK7) ---

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def require_admin_key(key: str | None = Security(admin_key_header)) -> None:
    if not config.ADMIN_API_KEY or key is None or not secrets.compare_digest(key, config.ADMIN_API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Saknad eller felaktig admin-nyckel")


class OrderStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    shopify_order_id: str
    shopify_order_no: str | None
    correlation_id: str
    status: str
    attempts: int
    last_error: str | None
    erp_order_id: int | None
    received_at: datetime
    updated_at: datetime


@app.get("/admin/orders", response_model=list[OrderStatusOut], tags=["Admin"],
         dependencies=[Depends(require_admin_key)])
def list_orders(status_filter: str | None = None, limit: int = 50):
    """Senaste ordrarna, valfritt filtrerade på status (mottagen, skickad, klar, fel)."""
    query = select(OrderStatus).order_by(OrderStatus.received_at.desc()).limit(min(limit, 500))
    if status_filter:
        query = query.where(OrderStatus.status == status_filter)
    with SessionLocal() as db:
        return db.scalars(query).all()


@app.get("/admin/orders/{shopify_order_id}", response_model=OrderStatusOut, tags=["Admin"],
         dependencies=[Depends(require_admin_key)])
def get_order(shopify_order_id: str):
    """Status för en order."""
    with SessionLocal() as db:
        row = order_status.get(db, shopify_order_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordern finns inte")
    return row
