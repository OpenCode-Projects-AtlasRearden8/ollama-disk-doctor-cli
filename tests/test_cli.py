# ollama-disk-doctor tests.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

import json

import pytest

from ollama_disk_doctor import __version__
from ollama_disk_doctor.cli import build_arg_parser, main, resolve_scan_targets
from ollama_disk_doctor.rules import Rules


class TestResolveScanTargets:
    def test_defaults(self):
        args = build_arg_parser().parse_args(["list"])
        ollama, caches = resolve_scan_targets(args, Rules())
        assert "~" in ollama
        assert any("huggingface" in c for c in caches)

    def test_cli_wins_over_rules(self):
        args = build_arg_parser().parse_args(
            ["--ollama-dir", "/custom/models", "--cache-dir", "/cache/x", "list"]
        )
        rules = Rules()
        rules.ollama_models_dir = "/rules/models"
        rules.cache_dirs = ["/rules/cache"]
        ollama, caches = resolve_scan_targets(args, rules)
        assert ollama == "/custom/models"
        assert caches == ["/cache/x"]

    def test_rules_used_when_no_cli(self):
        args = build_arg_parser().parse_args(["list"])
        rules = Rules()
        rules.ollama_models_dir = "/rules/models"
        rules.cache_dirs = ["/rules/cache"]
        ollama, caches = resolve_scan_targets(args, rules)
        assert ollama == "/rules/models"
        assert caches == ["/rules/cache"]


class TestCliRuns:
    def test_list_on_empty_machine(self, tmp_path, capsys):
        target = tmp_path / "nothing-here"
        rc = main(["list", "--ollama-dir", str(target),
                   "--cache-dir", str(tmp_path / "no-cache")])
        out = capsys.readouterr().out
        assert rc == 0
        assert "No models found" in out

    def test_list_reports_model(self, tmp_path, capsys):
        store = tmp_path / "models"
        make_model(store)
        rc = main(["list", "--ollama-dir", str(store)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "demo" in out
        assert "█" in out
        assert "*STALE*" in out
        assert "Reclaimable estimate" in out

    def test_list_json(self, tmp_path, capsys):
        store = tmp_path / "models"
        make_model(store)
        rc = main(["list", "--json", "--ollama-dir", str(store),
                   "--cache-dir", str(tmp_path / "no-cache")])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["models"][0]["name"].endswith("demo:latest")
        assert payload["total_bytes"] == 10 * 1024 * 1024

    def test_plan_prints_not_executes(self, tmp_path, capsys):
        store = tmp_path / "models"
        make_model(store)
        rc = main(
            ["plan", "--ollama-dir", str(store),
             "--cache-dir", str(tmp_path / "no-cache"),
             "--archive-dir", str(tmp_path / "archive")]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "DRY RUN ONLY" in out
        assert 'ollama rm "registry.ocr.io/library/demo:latest"' in out
        assert 'mkdir -p' in out
        # the "archive" target must not have been created by us
        assert not (tmp_path / "archive").exists()

    def test_dirs_command(self, capsys):
        rc = main(["--ollama-dir", "/x", "--cache-dir", "/y", "dirs"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "/x" in out and "/y" in out

    def test_bad_rules_file_rc2(self, tmp_path, capsys):
        rc = main(["--rules", str(tmp_path / "missing.toml"), "list"])
        err = capsys.readouterr().err
        assert rc == 2
        assert "error" in err

    def test_days_override_flags_fresh_model(self, tmp_path, capsys):
        store = tmp_path / "models"
        make_model(store, age_days=5)
        out_list = main(["list", "--days", "3", "--ollama-dir", str(store)])
        out = capsys.readouterr().out
        assert out_list == 0
        assert "*STALE*" in out

    def test_delete_plan_flag(self, tmp_path, capsys):
        store = tmp_path / "models"
        make_model(store)
        rc = main(["plan", "--action", "delete", "--ollama-dir", str(store)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "DRY RUN ONLY" in out
        assert 'ollama rm "registry.ocr.io/library/demo:latest"' in out

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert __version__ in capsys.readouterr().out


def make_model(store, age_days: float = 300.0):
    """Local fixture builder: a single fake Ollama model inside ``store``."""
    from conftest import make_ollama_model

    make_ollama_model(
        store, "registry.ocr.io", "library", "demo", "latest",
        [("e" * 64, 10 * 1024 * 1024)],
        age_days=age_days,
    )
