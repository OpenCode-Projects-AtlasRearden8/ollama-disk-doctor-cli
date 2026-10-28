# ollama-disk-doctor: friendly disk usage for local AI models.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

"""Rules file support: how stale is "untouched for months", where to archive.

Rules are plain TOML (stdlib ``tomllib``). CLI flags always win over the rules
file; the rules file wins over built-in defaults. See ``rules.example.toml``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_RULES_FILE = "rules.toml"
DEFAULT_STALE_DAYS = 90
DEFAULT_ARCHIVE_DIR = "~/.ollama-archive"


@dataclass
class Rules:
    stale_days: int = DEFAULT_STALE_DAYS
    ollama_models_dir: str | None = None  # None => only CLI/default handling
    cache_dirs: list[str] = field(default_factory=list)
    archive_dir: str = DEFAULT_ARCHIVE_DIR
    bar_width: int = 40
    source: str = "defaults"

    @classmethod
    def load(cls, path: str | Path | None) -> "Rules":
        """Load rules from TOML. Missing file => defaults; bad TOML raises ValueError."""
        if path is None:
            return cls()
        rules_path = Path(path).expanduser()
        if not rules_path.is_file():
            raise ValueError(f"rules file not found: {rules_path}")
        try:
            data = tomllib.loads(rules_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"rules file is not valid TOML ({rules_path}): {exc}") from exc
        rules = cls(source=str(rules_path))
        stale = data.get("stale_days")
        if stale is not None:
            if not isinstance(stale, int) or stale < 0:
                raise ValueError(f"stale_days must be a non-negative integer, got {stale!r}")
            rules.stale_days = stale
        paths = data.get("paths", {})
        if isinstance(paths, dict):
            ollama = paths.get("ollama_models_dir")
            if ollama is not None:
                if not isinstance(ollama, str) or not ollama.strip():
                    raise ValueError("paths.ollama_models_dir must be a non-empty string")
                rules.ollama_models_dir = ollama
            cache = paths.get("cache_dirs")
            if cache is not None:
                if not isinstance(cache, list) or not all(isinstance(c, str) for c in cache):
                    raise ValueError("paths.cache_dirs must be a list of strings")
                rules.cache_dirs = list(cache)
            archive = paths.get("archive_dir")
            if archive is not None:
                if not isinstance(archive, str) or not archive.strip():
                    raise ValueError("paths.archive_dir must be a non-empty string")
                rules.archive_dir = archive
        look = data.get("look")
        if isinstance(look, dict):
            width = look.get("bar_width")
            if width is not None:
                if not isinstance(width, int) or width <= 0:
                    raise ValueError("look.bar_width must be a positive integer")
                rules.bar_width = width
        return rules
