"""Startdata: samma artiklar och saldon som i webshoppen (docs/testdata/shopify-produkter.csv)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article

ARTICLES = [
    ("SB-TSH-001", "Basic t-shirt vit", 25),
    ("SB-TSH-002", "Basic t-shirt svart", 30),
    ("SB-HOD-001", "Hoodie grå", 12),
    ("SB-JNS-001", "Jeans straight blå", 15),
    ("SB-KNT-001", "Stickad tröja beige", 8),
    ("SB-CHN-001", "Chinos khaki", 10),
    ("SB-JKT-001", "Jeansjacka", 5),
    ("SB-ACC-001", "Mössa svart", 40),
]


def seed_articles(db: Session) -> None:
    """Lägger in artiklarna om tabellen är tom. Körs vid start."""
    if db.scalar(select(Article).limit(1)) is not None:
        return
    db.add_all(Article(article_no=no, name=name, stock_qty=qty) for no, name, qty in ARTICLES)
    db.commit()
