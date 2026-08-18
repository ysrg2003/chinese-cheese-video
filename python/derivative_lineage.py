"""Compatibility facade for the reusable derivative-lineage capsule."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from systems.derivative_lineage import build_lineage_metadata, parent_fingerprint, unused_windows, window_fingerprint

__all__ = ["build_lineage_metadata", "parent_fingerprint", "unused_windows", "window_fingerprint"]
