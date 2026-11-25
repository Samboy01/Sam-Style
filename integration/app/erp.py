"""Anrop till mini-ERP:t."""

import httpx

from . import config


def create_order(erp_order: dict) -> httpx.Response:
    """POST /orders. Kastar httpx.HTTPError (t.ex. timeout) om ERP:t inte går att nå."""
    return httpx.post(
        f"{config.ERP_URL}/orders",
        json=erp_order,
        headers={"X-API-Key": config.ERP_API_KEY},
        timeout=config.ERP_TIMEOUT_SECONDS,
    )
