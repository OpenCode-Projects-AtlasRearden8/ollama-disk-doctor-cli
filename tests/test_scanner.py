# ollama-disk-doctor tests.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

import os
import time

from conftest import make_cache_model, make_ollama_model
from ollama_disk_doctor.models import ModelInfo
from ollama_disk_doctor.scanner import (
    human_size,
    scan_ollama,
    scan_openai_cache,
)


class TestHumanSize:
    def test_bytes(self):
        assert human_size(0) == "0 B"

    def test_gib(self):
        assert human_size(int(4.7 * 1024 ** 3)).endswith("GiB")


class TestScanOllama:
    def test_names_and_sizes(self, tmp_path):
        store = tmp_path / "models"
        make_ollama_model(
            store, "registry.ocr.io", "library", "tiny", "latest",
            [("a" * 64, 100), ("b" * 64, 50)],
        )
        models = scan_ollama(store)
        assert len(models) == 1
        m = models[0]
        assert m.name == "registry.ocr.io/library/tiny:latest"
        assert m.size_bytes == 150
        assert m.source == "ollama"
        assert m.missing_blobs == 0

    def test_missing_blobs_counted(self, tmp_path):
        store = tmp_path / "models"
        make_ollama_model(
            store, "registry.ocr.io", "library", "ghost", "latest", [("c" * 64, 999)]
        )
        (store / "blobs" / ("sha256-" + "c" * 64)).unlink()  # pretend the blob vanished
        models = scan_ollama(store)
        m = models[0]
        assert m.size_bytes == 999  # still counted from manifest, flagged missing
        assert m.missing_blobs == 1

    def test_unclaimed_blobs_reported(self, tmp_path):
        store = tmp_path / "models"
        blobs_dir = store / "blobs"
        blobs_dir.mkdir(parents=True)
        blob = blobs_dir / ("sha256-" + "d" * 64)
        blob.write_bytes(b"\x00" * 200)
        os.utime(blob, (time.time() - 400 * 86400, time.time() - 400 * 86400))
        models = scan_ollama(store)
        assert models[0].name == "(unclaimed Ollama blobs)"
        assert models[0].size_bytes == 200

    def test_missing_dir_returns_empty(self, tmp_path):
        assert scan_ollama(tmp_path / "nope") == []

    def test_bad_json_manifest_surface(self, tmp_path):
        store = tmp_path / "models"
        bad = store / "manifests" / "reg" / "m" / "latest"
        bad.parent.mkdir(parents=True)
        bad.write_text("{not json")
        models = scan_ollama(store)
        assert models[0].name == "reg/m:latest (unreadable manifest)"
        assert any("manifest" in note for note in models[0].notes)


class TestScanOpenAICache:
    def test_groups_by_top_level_dir(self, tmp_path):
        cache = tmp_path / "hub"
        make_cache_model(
            cache, "models--meta-llama--Llama-3.2-1B",
            [("snapshots/a/weights.bin", 300), ("blobs/zzz", 50)],
        )
        make_cache_model(cache, "other-model", [("f", 10)])
        models = scan_openai_cache(cache)
        names = {m.name for m in models}
        assert names == {"models--meta-llama--Llama-3.2-1B", "other-model"}
        sizes = {m.name: m.size_bytes for m in models}
        assert sizes["models--meta-llama--Llama-3.2-1B"] == 350
        assert sizes["other-model"] == 10

    def test_loose_files_grouped(self, tmp_path):
        cache = tmp_path / "openai"
        cache.mkdir()
        (cache / "embedding.npy").write_bytes(b"\x00" * 32)
        models = scan_openai_cache(cache)
        assert models[0].name == "(top-level files)"
        assert models[0].size_bytes == 32

    def test_missing_dir_returns_empty(self, tmp_path):
        assert scan_openai_cache(tmp_path / "nope") == []


class TestModelInfo:
    def test_stale_flag(self):
        m = ModelInfo(name="x", source="s", path="/tmp", size_bytes=1,
                      last_modified=time.time() - 100 * 86400)
        assert m.is_stale(90)
        assert not m.is_stale(200)
