"""Shared sample paths for tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
SAMPLES_SQL = SAMPLES / "sql"


def sample_sql(name: str) -> Path:
    """Resolve a sample .sql file under ``samples/sql/`` or ``samples/``."""
    for base in (SAMPLES_SQL, SAMPLES):
        path = base / name
        if path.exists():
            return path
    raise FileNotFoundError(f"sample not found: {name}")
