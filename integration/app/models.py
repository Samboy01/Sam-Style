"""Tabellen order_status: var varje order befinner sig i flödet (FK7)."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

# Statusar enligt integrationsspecifikationen, avsnitt 6
RECEIVED = "mottagen"  # webhooken har tagit emot ordern och lagt den på kön
SENT = "skickad"       # workern försöker skicka ordern till ERP:t
DONE = "klar"          # ordern finns i ERP:t
FAILED = "fel"         # ordern ligger i felkön


class OrderStatus(Base):
    __tablename__ = "order_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unik: samma Shopify-order registreras bara en gång (IFK2).
    shopify_order_id: Mapped[str] = mapped_column(String(50), unique=True)
    shopify_order_no: Mapped[str | None] = mapped_column(String(50))
    correlation_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    erp_order_id: Mapped[int | None]
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
