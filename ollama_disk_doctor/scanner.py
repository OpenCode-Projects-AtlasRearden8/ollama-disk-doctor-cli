# ollama-disk-doctor: friendly disk usage for local AI models.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

"""Scan Ollama model stores and OpenAI-compatible caches for models on disk.

Never modifies anything: scanning is read-only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import ModelInfo


def human_size(n: float) -> str:
    """Human-readable size, e.g. 4.7 GiB. Pure formatting, no side effects."""
    step = 1024.0
    size = float(n)
    if size < step:
        return f"{int(size)} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        size /= step
        if size < step:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PiB"


def _max_mtime(paths, root_mtime: float | None) -> float:
    newest = root_mtime if root_mtime is not None else 0.0
    for p in paths:
        try:
            newest = max(newest, p.lstat().st_mtime)
        except OSError:
            continue
    return newest or 0.0


def scan_ollama(models_root: str | os.PathLike) -> list[ModelInfo]:
    """Scan an Ollama models directory (default ~/.ollama/models).

    Reads manifest JSON files under ``manifests/`` and sums the blobs each
    model references under ``blobs/``. Falls back to listing raw blobs when
    manifests are missing, so nothing on disk stays invisible.
    """
    root = Path(models_root).expanduser()
    models: list[ModelInfo] = []
    if not root.is_dir():
        return models

    manifests_dir = root / "manifests"
    blobs_dir = root / "blobs"
    claimed: set[Path] = set()

    if manifests_dir.is_dir():
        for manifest_path in sorted(manifests_dir.rglob("*")):
            if not manifest_path.is_file():
                continue
            rel = manifest_path.relative_to(manifests_dir).parts
            # Expected layout: <registry>/<namespace?>/<model>/<tag>
            if len(rel) >= 2:
                tag = rel[-1]
                model_name = "/".join(rel[:-1]) + ":" + tag
            else:
                model_name = rel[0] if rel else manifest_path.name
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                models.append(
                    ModelInfo(
                        name=f"{model_name} (unreadable manifest)",
                        source="ollama",
                        path=str(manifest_path),
                        size_bytes=manifest_path.stat().st_size,
                        last_modified=manifest_path.stat().st_mtime,
                        notes=["manifest could not be parsed as JSON"],
                    )
                )
                continue
            digests: dict[str, int] = {}
            for layer in data.get("layers", []) or []:
                digest = layer.get("digest", "")
                if digest:
                    digests[digest] = digests.get(digest, 0) + int(
                        layer.get("size", 0) or 0
                    )
            total = 0
            missing = 0
            for digest, size in digests.items():
                blob = blobs_dir / digest.replace(":", "-")
                claimed.add(blob)
                if blob.is_file():
                    try:
                        size = blob.stat().st_size
                    except OSError:
                        missing += 1
                else:
                    missing += 1
                total += size
            models.append(
                ModelInfo(
                    name=model_name,
                    source="ollama",
                    path=str(manifests_dir.parent / "blobs"),
                    size_bytes=total,
                    last_modified=_max_mtime(
                        [manifest_path] + [
                            blobs_dir / d.replace(":", "-") for d in digests
                        ],
                        None,
                    ),
                    missing_blobs=missing,
                    files=len(digests),
                )
            )

    leftover = [p for p in blobs_dir.iterdir() if p.is_file()] if blobs_dir.is_dir() else []
    unclaimed = [p for p in leftover if p not in claimed]
    if unclaimed:
        total = sum(p.stat().st_size for p in unclaimed if p.is_file())
        models.append(
            ModelInfo(
                name="(unclaimed Ollama blobs)",
                source="ollama",
                path=str(blobs_dir),
                size_bytes=total,
                last_modified=_max_mtime(unclaimed, None),
                files=len(unclaimed),
                notes=[
                    f"{len(unclaimed)} blob(s) not referenced by any manifest "
                    "(candidates for cleanup, verify with `ollama list` first)"
                ],
            )
        )
    return models


def scan_openai_cache(cache_root: str | os.PathLike, source_name: str | None = None) -> list[ModelInfo]:
    """Scan an OpenAI-compatible / HuggingFace-style cache directory.

    Groups files by their first-level directory (e.g. the ``models--*`` folders
    of a HuggingFace cache, or plain model folders). Any loose files directly
    under the root are grouped as "(top-level files)".
    """
    root = Path(cache_root).expanduser()
    label = source_name or f"cache:{root.name}"
    models: list[ModelInfo] = []
    if not root.is_dir():
        return models

    groups: dict[Path, list[Path]] = {}
    loose: list[Path] = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            groups[entry] = list(entry.rglob("*"))
        else:
            loose.append(entry)

    for base, files in groups.items():
        files = [f for f in files if f.is_file()]
        if not files:
            continue
        total = sum(f.stat().st_size for f in files)
        models.append(
            ModelInfo(
                name=base.name,
                source=label,
                path=str(base),
                size_bytes=total,
                last_modified=_max_mtime(files, None),
                files=len(files),
            )
        )
    if loose:
        models.append(
            ModelInfo(
                name="(top-level files)",
                source=label,
                path=str(root),
                size_bytes=sum(f.stat().st_size for f in loose),
                last_modified=_max_mtime(loose, None),
                files=len(loose),
            )
        )
    return models
