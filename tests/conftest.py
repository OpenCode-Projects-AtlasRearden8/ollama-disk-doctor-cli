# ollama-disk-doctor tests: helpers for building fake Ollama stores in tmp paths.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

"""Shared tmp-path fixtures. Everything here builds throwaway fixtures under
tmp_path - never the user's real model directories."""

from __future__ import annotations

import json
import os
import time


def make_blob(blobs_dir, digest_hex: str, size: int) -> object:
    blobs_dir.mkdir(parents=True, exist_ok=True)
    blob = blobs_dir / f"sha256-{digest_hex}"
    blob.write_bytes(b"\x00" * size)
    return blob


def make_ollama_model(
    store,
    registry: str,
    namespace: str,
    model: str,
    tag: str,
    blobs: list[tuple[str, int]],
    age_days: float = 1.0,
) -> None:
    """Build a realistic Ollama store fixture rooted at ``store``.

    blobs is [(digest_hex, size), ...]; mtimes are backdated by age_days.
    """
    manifests_root = store / "manifests" / registry
    if namespace:
        manifest_dir = manifests_root / namespace / model
    else:
        manifest_dir = manifests_root / model
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / tag
    layers = [
        {
            "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
            "digest": f"sha256:{digest_hex}",
            "size": size,
        }
        for digest_hex, size in blobs
    ]
    manifest.write_text(json.dumps({"layers": layers}), encoding="utf-8")
    blobs_dir = store / "blobs"
    old = time.time() - age_days * 86400
    for digest_hex, _size in blobs:
        blob = make_blob(blobs_dir, digest_hex, _size)
        os.utime(blob, (old, old))
    os.utime(manifest, (old, old))


def make_cache_model(cache_dir, model_dir_name: str, files: list[tuple[str, int]], age_days: float = 1.0) -> None:
    base = cache_dir / model_dir_name
    base.mkdir(parents=True, exist_ok=True)
    old = time.time() - age_days * 86400
    for name, size in files:
        f = base / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"\x00" * size)
        os.utime(f, (old, old))
