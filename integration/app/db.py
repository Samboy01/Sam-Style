"""Integrationens egen databas."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def create_tables() -> None:
    from . import models  # noqa: F401  (registrerar tabellerna)

    Base.metadata.create_all(engine)
