"""Gemensam testkonfiguration: gör integrationstjänstens kod importerbar och sätter testinställningar."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "integration"))

# Testinställningar – inte de riktiga. Måste sättas innan app.config importeras.
os.environ.setdefault("SHOPIFY_WEBHOOK_SECRET", "test-hemlighet")
os.environ.setdefault("INTEGRATION_ADMIN_KEY", "test-admin")
# Testerna använder en SQLite-fil i stället för PostgreSQL, så att de går att köra utan Docker.
os.environ.setdefault("INTEGRATION_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")


@pytest.fixture(autouse=True)
def clean_db():
    """Tom statustabell i varje test."""
    from app.db import Base, create_tables, engine

    create_tables()
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
