# ollama-disk-doctor: friendly disk usage for local AI models.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

"""Core data model shared by scanner, report, and plan modules."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ModelInfo:
    """One scanned model directory (or Ollama manifest)."""

    name: str
    source: str          # e.g. "ollama", "huggingface-cache", "openai-cache"
    path: str
    size_bytes: int
    last_modified: float  # unix timestamp (max mtime seen in the model)
    missing_blobs: int = 0  # ollama blobs referenced but not on disk
    files: int = field(default=0)
    notes: list[str] = field(default_factory=list)

    @property
    def age_days(self) -> float:
        return max(0.0, (time.time() - self.last_modified) / 86400.0)

    def is_stale(self, stale_days: int) -> bool:
        return self.age_days >= stale_days

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["age_days"] = round(self.age_days, 1)
        return d
