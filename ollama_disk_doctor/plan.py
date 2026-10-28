# ollama-disk-doctor: friendly disk usage for local AI models.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

"""Build a move-or-delete plan. This module only ever *prints* steps.

Nothing here touches your files - no shutil, no os.remove, no mv/rm execution.
For Ollama-managed models the plan prints `ollama rm <name>` because Ollama's
blob store is shared between models; mv/rm steps are only printed for
plain cache directories the tool can safely name.
"""

from __future__ import annotations

import time
from typing import Any

from .models import ModelInfo
from .rules import Rules
from .scanner import human_size
from .report import reclaimable


def build_plan(models: list[ModelInfo], rules: Rules, action: str = "move") -> list[str]:
    """Return the plan as printable text lines. action is "move" or "delete"."""
    if action not in ("move", "delete"):
        raise ValueError(f"unknown action: {action!r} (use 'move' or 'delete')")

    stale = sorted(
        (m for m in models if m.is_stale(rules.stale_days)),
        key=lambda m: m.size_bytes,
        reverse=True,
    )
    label = "MOVE (to" if action == "move" else "DELETE"
    lines: list[str] = []
    lines.append("# ollama-disk-doctor plan - generated " + time.strftime("%Y-%m-%d %H:%M"))
    lines.append(f"# rules: flag models untouched {rules.stale_days}+ days as stale")
    lines.append("# DRY RUN ONLY: nothing was deleted or moved. Read every line first.")
    if not stale:
        lines.append("Nothing to do: no models meet the stale threshold.")
        lines.append(f"Nice - up to {human_size(reclaimable(models, rules.stale_days))} is already tidy.")
        return lines

    lines.append(f"# {len(stale)} stale model(s), {human_size(reclaimable(stale, rules.stale_days))} potential reclaim:")
    lines.append("")

    if action == "move":
        archive = str(rules.archive_dir)
        step = 1
        lines.append(f"1 ) mkdir -p \"{archive}\"")
        for m in stale:
            step += 1
            if m.source == "ollama":
                lines.append(
                    f"{step} ) ollama rm \"{m.name}\"   # {human_size(m.size_bytes)}, "
                    "untouched; Ollama-managed stores share blobs, so never mv blobs by hand"
                )
            else:
                lines.append(
                    f"{step} ) mv \"{m.path}\" \"{archive}/{m.name}\"   # "
                    f"{human_size(m.size_bytes)}, {m.source}"
                )
        lines.append(
            f"{step + 1} ) Run `ollama list` afterwards to confirm Ollama still sees what you want."
        )
    else:
        for step, m in enumerate(stale, start=1):
            if m.source == "ollama":
                lines.append(
                    f"{step} ) ollama rm \"{m.name}\"   # {human_size(m.size_bytes)}, "
                    f"untouched {m.age_days:.0f}d; (manifest under {m.path})"
                )
            else:
                lines.append(
                    f"{step} ) rm -rf \"{m.path}\"   # {human_size(m.size_bytes)}, {m.source}, name: {m.name}"
                )
        lines.append(
            "Tip: prefer `ollama rm <name>` for Ollama models - blobs are shared, "
            "never delete them by hand."
        )
    lines.append("")
    return lines


def attach_estimates(plan_lines: list[str], models: list[ModelInfo], rules: Rules) -> list[str]:
    """Prepend a summary block (kept separate so build_plan stays testable)."""
    total = sum(m.size_bytes for m in models)
    reclaim = reclaimable(models, rules.stale_days)
    summary = [
        f"Scanned {len(models)} model(s), {human_size(total)} total.",
        f"Plan targets stale models ({rules.stale_days}+ days untouched): "
        f"{human_size(reclaim)} potential reclaim.",
    ]
    return summary + [""] + plan_lines
