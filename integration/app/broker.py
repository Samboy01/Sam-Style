"""Kön (RabbitMQ): köer och hur meddelanden läggs på dem."""

import pika

from . import config

INCOMING = "orders.incoming"  # nya ordrar som väntar på att föras över
DEAD = "orders.dead"          # felkö: ordrar som inte gick att föra över


def connect() -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))


def declare_queues(channel) -> None:
    """Skapar köerna om de inte finns. durable = köerna överlever en omstart av RabbitMQ."""
    channel.queue_declare(queue=INCOMING, durable=True)
    channel.queue_declare(queue=DEAD, durable=True)


def publish(channel, queue: str, body: bytes, headers: dict) -> None:
    """Lägger ett meddelande på en kö.

    delivery_mode=2 betyder att meddelandet sparas på disk, så att det finns kvar
    även om RabbitMQ startas om (IFK1).
    """
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=body,
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            headers=headers,
        ),
        mandatory=True,
    )


def publish_order(body: bytes, headers: dict) -> None:
    """Används av webhooken: lägger en order på orders.incoming och väntar på kvitto.

    confirm_delivery gör att RabbitMQ bekräftar att meddelandet är sparat. Först då
    svarar webhooken 200 till Shopify. Om något går fel kastas ett undantag, webhooken
    svarar 503 och Shopify skickar ordern igen senare. Så försvinner ingen order.
    """
    connection = connect()
    try:
        channel = connection.channel()
        channel.confirm_delivery()
        declare_queues(channel)
        publish(channel, INCOMING, body, headers)
    finally:
        connection.close()
