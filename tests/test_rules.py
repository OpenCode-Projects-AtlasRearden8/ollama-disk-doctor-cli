# ollama-disk-doctor tests.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

import pytest

from ollama_disk_doctor.rules import Rules


def test_defaults():
    r = Rules.load(None)
    assert r.stale_days == 90
    assert r.bar_width == 40
    assert r.source == "defaults"


def test_load_example_toml():
    r = Rules.load("rules.example.toml")
    assert r.stale_days == 90
    assert r.archive_dir == "~/.ollama-archive"
    assert "~/.cache/openai" in r.cache_dirs


def test_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        Rules.load(tmp_path / "nope.toml")


def test_bad_toml_raises(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("stale_days = = 1")
    with pytest.raises(ValueError, match="not valid TOML"):
        Rules.load(bad)


def test_bad_stale_days_raises(tmp_path):
    bad = tmp_path / "rules.toml"
    bad.write_text('stale_days = "soon"')
    with pytest.raises(ValueError, match="non-negative"):
        Rules.load(bad)


def test_good_rules(tmp_path):
    f = tmp_path / "rules.toml"
    f.write_text(
        'stale_days = 30\n'
        '[paths]\nollama_models_dir = "/data/ollama"\n'
        'cache_dirs = ["/cache/a", "/cache/b"]\n'
        'archive_dir = "/archive"\n'
        '[look]\nbar_width = 20\n'
    )
    r = Rules.load(f)
    assert r.stale_days == 30
    assert r.ollama_models_dir == "/data/ollama"
    assert r.cache_dirs == ["/cache/a", "/cache/b"]
    assert r.archive_dir == "/archive"
    assert r.bar_width == 20
