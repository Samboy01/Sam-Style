"""Hur data ser ut in och ut ur API:et. FastAPI kontrollerar inkommande data mot dessa
och svarar automatiskt 422 om något inte stämmer (t.ex. qty som inte är ett heltal)."""

from datetime import datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Amount = Decimal  # belopp med två decimaler, skickas som text i JSON (t.ex. "199.00")


class OrderRowIn(BaseModel):
    article_no: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)
    qty: int = Field(gt=0)
    unit_price: Amount = Field(ge=0, max_digits=12, decimal_places=2)


class OrderIn(BaseModel):
    external_order_id: str = Field(min_length=1, max_length=50)
    external_order_no: str | None = Field(default=None, max_length=50)
    order_date: AwareDatetime
    currency: str = Field(pattern="^SEK$")
    customer_ref: str = Field(min_length=1, max_length=100)
    shipping_amount: Amount = Field(ge=0, max_digits=12, decimal_places=2)
    discount_amount: Amount = Field(ge=0, max_digits=12, decimal_places=2)
    total_amount: Amount = Field(ge=0, max_digits=12, decimal_places=2)
    rows: list[OrderRowIn] = Field(min_length=1)


class OrderRowOut(OrderRowIn):
    model_config = ConfigDict(from_attributes=True)
    row_no: int


class OrderOut(OrderIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    rows: list[OrderRowOut]


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    article_no: str
    name: str
    stock_qty: int
    updated_at: datetime


class StockUpdate(BaseModel):
    stock_qty: int = Field(ge=0)
