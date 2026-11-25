"""Tes evals dijalankan terpisah: backend/venv/Scripts/python -m pytest backend/evals/tests"""
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parents[1]
for p in (EVALS_DIR.parent, EVALS_DIR / "scripts"):  # backend/ dan backend/evals/scripts/
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
