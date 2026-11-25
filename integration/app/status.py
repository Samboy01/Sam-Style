"""Funktioner som flyttar en order mellan statusarna.

    mottagen ──▶ skickad ──▶ klar
                    │
                    └──▶ fel ──(omkörning, #14)──▶ skickad
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import DONE, FAILED, RECEIVED, SENT, OrderStatus


def get(db: Session, shopify_order_id: str) -> OrderStatus | None:
    return db.scalar(select(OrderStatus).where(OrderStatus.shopify_order_id == shopify_order_id))


def register_received(db: Session, shopify_order_id: str, shopify_order_no: str | None,
                      correlation_id: str) -> bool:
    """Registrerar en ny order som mottagen. Returnerar False om ordern redan finns (dubblett).

    Sparas inte (commit) här, så att webhooken kan ångra om ordern inte går att lägga på kön.
    """
    if get(db, shopify_order_id) is not None:
        return False
    db.add(OrderStatus(shopify_order_id=shopify_order_id, shopify_order_no=shopify_order_no,
                       correlation_id=correlation_id, status=RECEIVED))
    try:
        db.flush()
    except IntegrityError:
        # Två webhooks för samma order kom samtidigt och den andra hann före.
        db.rollback()
        return False
    return True


def mark_sent(db: Session, shopify_order_id: str, shopify_order_no: str | None, correlation_id: str) -> None:
    """Workern börjar skicka ordern. Räknar upp antal försök."""
    row = get(db, shopify_order_id)
    if row is None:
        # Workern kan hinna före webhookens commit: ordern ligger redan på kön men statusraden
        # är inte sparad än. Då försöker vi skapa raden. Databasen väntar tills webhookens
        # transaktion är klar och säger sedan att raden redan finns – då läser vi den i stället.
        try:
            with db.begin_nested():
                db.add(OrderStatus(shopify_order_id=shopify_order_id, shopify_order_no=shopify_order_no,
                                   correlation_id=correlation_id, status=RECEIVED, attempts=0))
        except IntegrityError:
            pass
        row = get(db, shopify_order_id)
    row.status = SENT
    row.attempts += 1
    db.commit()


def mark_done(db: Session, shopify_order_id: str, erp_order_id: int | None) -> None:
    row = get(db, shopify_order_id)
    row.status = DONE
    row.last_error = None
    if erp_order_id is not None:
        row.erp_order_id = erp_order_id
    db.commit()


def mark_failed(db: Session, shopify_order_id: str, reason: str) -> None:
    row = get(db, shopify_order_id)
    row.status = FAILED
    row.last_error = reason
    db.commit()
