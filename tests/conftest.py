"""Gemensam testkonfiguration: gör integrationstjänstens kod importerbar och sätter testinställningar."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "integration"))

# Testhemlighet – inte den riktiga. Måste sättas innan app.config importeras.
os.environ.setdefault("SHOPIFY_WEBHOOK_SECRET", "test-hemlighet")
