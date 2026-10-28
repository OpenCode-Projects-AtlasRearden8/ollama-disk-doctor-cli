# ollama-disk-doctor: friendly disk usage for local AI models.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

"""Rendering: sorted size listing, ASCII bar chart, JSON, and reclaim estimate."""

from __future__ import annotations

import json
import time
from typing import Any

from .models import ModelInfo
from .rules import Rules
from .scanner import human_size


def reclaimable(models: list[ModelInfo], stale_days: int) -> int:
    """Bytes recoverable by cleaning up models flagged stale by the rules."""
    return sum(m.size_bytes for m in models if m.is_stale(stale_days))


def _truncate(name: str, width: int) -> str:
    if len(name) <= width:
        return name
    return name[: width - 3] + "..."


def bar(size_bytes: int, max_size: int, bar_width: int) -> str:
    """ASCII bar proportional to size. Anything nonzero gets at least one block."""
    if max_size <= 0 or bar_width <= 0:
        return ""
    if size_bytes <= 0:
        return ""
    filled = max(1, round(size_bytes * bar_width / max_size))
    return "█" * filled


def render_report(models: list[ModelInfo], rules: Rules, as_json: bool = False) -> str:
    """Build the full friendly report text (bar chart + staleness flags + totals)."""
    if as_json:
        payload: dict[str, Any] = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "stale_days": rules.stale_days,
            "total_bytes": sum(m.size_bytes for m in models),
            "reclaimable_bytes": reclaimable(models, rules.stale_days),
            "models": [m.to_dict() for m in models],
        }
        return json.dumps(payload, indent=2)

    lines: list[str] = []
    if not models:
        lines.append("No models found in the directories I looked at.")
        lines.append("Nothing to clean today - enjoy the disk space you have!")
        return "\n".join(lines)

    models = sorted(models, key=lambda m: m.size_bytes, reverse=True)
    total = sum(m.size_bytes for m in models)
    reclaim = reclaimable(models, rules.stale_days)
    max_size = models[0].size_bytes
    name_width = min(40, max(len(_truncate(m.name, 40)) for m in models))

    lines.append(f"Models found: {len(models)}   Total: {human_size(total)}")
    lines.append(
        f"Untouched {rules.stale_days}+ days: "
        f"{sum(1 for m in models if m.is_stale(rules.stale_days))}   "
        f"Reclaimable estimate: {human_size(reclaim)}"
    )
    lines.append("(estimate = stale models only; your call - I never delete anything)")
    lines.append("")
    header = f"{'MODEL'.ljust(name_width)}  {'SIZE'.rjust(9)}  {'AGE'.rjust(10)}  BAR"
    lines.append(header)
    for m in models:
        name = _truncate(m.name, name_width)
        size = human_size(m.size_bytes).rjust(9)
        age = _format_age(m.age_days).rjust(10)
        flag = " *STALE*" if m.is_stale(rules.stale_days) else ""
        row = f"{name.ljust(name_width)}  {size}  {age}  {bar(m.size_bytes, max_size, rules.bar_width)}{flag}"
        if m.missing_blobs:
            row += f" ({m.missing_blobs} missing blob(s))"
        lines.append(row)
    return "\n".join(lines)


def _format_age(days: float) -> str:
    if days < 1:
        return "<1d"
    if days < 365:
        return f"{days:.0f}d"
    years = days / 365
    return f"{years:.1f}y"
