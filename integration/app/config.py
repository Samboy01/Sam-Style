"""Inställningar som läses från miljövariabler (se .env.example i projektroten)."""

import os

# Hemligheten som Shopify signerar webhooks med. Tom = alla webhooks avvisas.
SHOPIFY_WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")
