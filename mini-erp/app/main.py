"""Mini-ERP: ett enkelt affärssystem som integrationen skickar ordrar till."""

import asyncio
import secrets
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config
from .database import Base, SessionLocal, engine, get_db
from .models import Article, Order, OrderRow
from .schemas import ArticleOut, OrderIn, OrderOut, StockUpdate
from .seed import seed_articles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Skapa tabellerna och lägg in startdata när tjänsten startar.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_articles(db)
    yield


app = FastAPI(
    title="Mini-ERP",
    description="Enkelt affärssystem för Sam Bolaget. Kräver API-nyckel i headern X-API-Key.",
    version="0.1.0",
    lifespan=lifespan,
)

# Anrop som felbrytaren inte påverkar, så att man alltid kan se testsidan och hälsokontrollen.
UNAFFECTED_PATHS = {"/health", "/docs", "/openapi.json"}


@app.middleware("http")
async def failure_switch(request: Request, call_next):
    """Felbrytare: låtsas att systemet är nere eller långsamt (styrs av ERP_FAILURE_MODE)."""
    if request.url.path not in UNAFFECTED_PATHS:
        if config.FAILURE_MODE == "down":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Affärssystemet är tillfälligt nere (felbrytare)"},
            )
        if config.FAILURE_MODE == "slow":
            await asyncio.sleep(config.SLOW_SECONDS)
    return await call_next(request)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    """Avvisar anrop utan rätt API-nyckel."""
    if api_key is None or not secrets.compare_digest(api_key, config.API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Saknad eller felaktig API-nyckel")


@app.get("/health", tags=["Drift"])
def health():
    """Hälsokontroll för Docker. Kräver ingen API-nyckel."""
    return {"status": "ok"}


@app.post(
    "/orders",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Ordrar"],
    dependencies=[Depends(require_api_key)],
    responses={
        409: {"description": "Ordern finns redan (samma external_order_id)"},
        422: {"description": "Ogiltig order, t.ex. okänt artikelnummer"},
    },
)
def create_order(order_in: OrderIn, db: Session = Depends(get_db)):
    """Skapar en order och drar av antalet från lagersaldot."""
    existing = db.scalar(select(Order).where(Order.external_order_id == order_in.external_order_id))
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Ordern finns redan", "order_id": existing.id},
        )

    # Kontrollera att alla artiklar finns, och lås dem medan saldot ändras.
    article_nos = {row.article_no for row in order_in.rows}
    articles = {
        a.article_no: a
        for a in db.scalars(
            select(Article).where(Article.article_no.in_(article_nos)).with_for_update()
        )
    }
    unknown = sorted(article_nos - articles.keys())
    if unknown:
        raise HTTPException(422, f"Okänt artikelnummer: {', '.join(unknown)}")

    order = Order(**order_in.model_dump(exclude={"rows"}))
    for row_no, row in enumerate(order_in.rows, start=1):
        order.rows.append(OrderRow(row_no=row_no, **row.model_dump()))
        article = articles[row.article_no]
        article.stock_qty -= row.qty  # kan bli negativt (restorder)
        article.updated_at = func.now()

    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        # Två anrop med samma order kom samtidigt och det andra hann före.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "Ordern finns redan"})
    db.refresh(order)
    return order


@app.get(
    "/orders/{order_id}",
    response_model=OrderOut,
    tags=["Ordrar"],
    dependencies=[Depends(require_api_key)],
)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Hämtar en order med dess rader."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ordern finns inte")
    return order


@app.get(
    "/articles",
    response_model=list[ArticleOut],
    tags=["Artiklar"],
    dependencies=[Depends(require_api_key)],
)
def list_articles(db: Session = Depends(get_db)):
    """Listar alla artiklar med saldo."""
    return db.scalars(select(Article).order_by(Article.article_no)).all()


@app.get(
    "/articles/changed",
    response_model=list[ArticleOut],
    tags=["Artiklar"],
    dependencies=[Depends(require_api_key)],
)
def list_changed_articles(since: datetime, db: Session = Depends(get_db)):
    """Listar artiklar vars saldo har ändrats efter `since` (används av lagersynken)."""
    return db.scalars(
        select(Article).where(Article.updated_at > since).order_by(Article.updated_at)
    ).all()


@app.put(
    "/articles/{article_no}/stock",
    response_model=ArticleOut,
    tags=["Artiklar"],
    dependencies=[Depends(require_api_key)],
)
def update_stock(article_no: str, update: StockUpdate, db: Session = Depends(get_db)):
    """Sätter nytt lagersaldo, t.ex. efter inleverans eller inventering."""
    article = db.get(Article, article_no)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artikeln finns inte")
    article.stock_qty = update.stock_qty
    article.updated_at = func.now()
    db.commit()
    db.refresh(article)
    return article
