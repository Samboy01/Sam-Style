"""Worker: hämtar ordrar från kön, mappar dem och skickar dem till mini-ERP:t.

Startas som en egen process: python -m app.worker
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import pika.exceptions

from . import broker, erp
from . import status as order_status
from .db import SessionLocal, create_tables
from .mapping import MappingError, map_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
log = logging.getLogger("worker")


@dataclass
class Outcome:
    ok: bool              # True = klar (eller fanns redan). False = till felkön.
    reason: str = ""      # felorsak som visas i felkön
    erp_order_id: int | None = None


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail"))
    except ValueError:
        return response.text[:200]


def handle_order(body: bytes, create_order=erp.create_order) -> Outcome:
    """Behandlar en order från kön (flöde 1, steg 5–6). Pratar inte med kön själv,
    så att den går att testa utan RabbitMQ."""
    try:
        erp_order = map_order(json.loads(body))
    except ValueError as e:  # ogiltig JSON
        return Outcome(False, f"Ogiltig JSON: {e}")
    except MappingError as e:
        return Outcome(False, str(e))

    try:
        response = create_order(erp_order)
    except httpx.HTTPError as e:
        # TODO (#14): tillfälligt fel – försök igen efter 1, 5 och 15 minuter
        return Outcome(False, f"ERP svarar inte: {type(e).__name__}")

    if response.status_code == 201:
        return Outcome(True, erp_order_id=response.json().get("id"))
    if response.status_code == 409:
        # Ordern finns redan i ERP:t: behandlas som lyckat (IFK2).
        return Outcome(True, "Fanns redan i ERP")
    # TODO (#14): skilj på tillfälliga (5xx) och permanenta (4xx) fel
    return Outcome(False, f"ERP svarade {response.status_code}: {_detail(response)}")


def on_message(channel, method, properties, body: bytes) -> None:
    headers = dict(properties.headers or {})
    order_id = headers.get("shopify_order_id")
    ids = f"shopify_order_id={order_id} correlation_id={headers.get('correlation_id')}"

    with SessionLocal() as db:
        order_status.mark_sent(db, order_id, headers.get("shopify_order_no"), headers.get("correlation_id"))

    outcome = handle_order(body)

    if outcome.ok:
        with SessionLocal() as db:
            order_status.mark_done(db, order_id, outcome.erp_order_id)
        log.info("Order klar: %s erp_order_id=%s %s", ids, outcome.erp_order_id, outcome.reason)
    else:
        headers["error_reason"] = outcome.reason
        headers["failed_at"] = datetime.now(timezone.utc).isoformat()
        broker.publish(channel, broker.DEAD, body, headers)
        with SessionLocal() as db:
            order_status.mark_failed(db, order_id, outcome.reason)
        log.warning("Order till felkön: %s orsak=%s", ids, outcome.reason)

    # Bekräfta först när ordern är klar eller ligger säkert i felkön.
    # Kraschar workern innan dess levereras meddelandet igen, så inget försvinner.
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    create_tables()
    while True:
        try:
            connection = broker.connect()
            channel = connection.channel()
            broker.declare_queues(channel)
            channel.basic_qos(prefetch_count=1)  # en order i taget
            channel.basic_consume(queue=broker.INCOMING, on_message_callback=on_message)
            log.info("Worker startad, väntar på ordrar i %s", broker.INCOMING)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            log.warning("Kan inte ansluta till kön, försöker igen om 5 sekunder")
            time.sleep(5)


if __name__ == "__main__":
    main()
