"""Inställningar som läses från miljövariabler (se .env.example i projektroten)."""

import os

DATABASE_URL = os.environ["ERP_DATABASE_URL"]
API_KEY = os.environ["ERP_API_KEY"]

# Felbrytare för att demonstrera felhantering:
#   none = normal drift
#   down = alla API-anrop svarar 503 Service Unavailable
#   slow = alla API-anrop väntar ERP_SLOW_SECONDS sekunder innan de svarar
FAILURE_MODE = os.environ.get("ERP_FAILURE_MODE", "none").lower()
SLOW_SECONDS = float(os.environ.get("ERP_SLOW_SECONDS", "10"))
