#!/usr/bin/env python3
"""Write docs/version.json from sql_sp_harness.__version__ (single source of truth)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sql_sp_harness import __version__

OUT = ROOT / "docs" / "version.json"
OUT.write_text(
    json.dumps({"version": __version__}, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Wrote {OUT.relative_to(ROOT)} ({__version__})")
