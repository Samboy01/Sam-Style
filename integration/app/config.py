"""Inställningar som läses från miljövariabler (se .env.example i projektroten)."""

import os

# Hemligheten som Shopify signerar webhooks med. Tom = alla webhooks avvisas.
SHOPIFY_WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")

# Kön
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Mini-ERP (används av workern)
ERP_URL = os.environ.get("ERP_URL", "http://localhost:8001")
ERP_API_KEY = os.environ.get("ERP_API_KEY", "")
ERP_TIMEOUT_SECONDS = float(os.environ.get("ERP_TIMEOUT_SECONDS", "10"))
