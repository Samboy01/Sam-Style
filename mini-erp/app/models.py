"""Databastabeller: articles, orders och order_rows."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Article(Base):
    __tablename__ = "articles"

    article_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    stock_qty: Mapped[int]
    # Uppdateras vid varje saldoändring. Behövs för deltasynken (GET /articles/changed).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unik: samma webshop-order kan aldrig skapas två gånger (IFK2).
    external_order_id: Mapped[str] = mapped_column(String(50), unique=True)
    external_order_no: Mapped[str | None] = mapped_column(String(50))
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    currency: Mapped[str] = mapped_column(String(3))
    customer_ref: Mapped[str] = mapped_column(String(100))
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rows: Mapped[list["OrderRow"]] = relationship(
        back_populates="order", order_by="OrderRow.row_no", cascade="all, delete-orphan"
    )


class OrderRow(Base):
    __tablename__ = "order_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    row_no: Mapped[int]
    article_no: Mapped[str] = mapped_column(ForeignKey("articles.article_no"))
    description: Mapped[str | None] = mapped_column(String(200))
    qty: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[Order] = relationship(back_populates="rows")
