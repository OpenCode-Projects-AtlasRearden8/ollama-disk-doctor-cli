# ollama-disk-doctor tests.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

import time

import pytest

from ollama_disk_doctor.models import ModelInfo
from ollama_disk_doctor.plan import attach_estimates, build_plan
from ollama_disk_doctor.rules import Rules
import time

def make_model(name, mb, age_days, source="ollama"):
    return ModelInfo(
        name=name,
        source=source,
        path=f"/fake/{name}",
        size_bytes=mb * 1024 * 1024,
        last_modified=time.time() - age_days * 86400,
    )


class TestBuildPlan:
    def test_move_plan_has_ollama_rm_for_ollama_models(self):
        rules = Rules()
        rules.archive_dir = "/archive"
        plan = build_plan([make_model("old", 10, 200, source="ollama")], rules, "move")
        text = "\n".join(plan)
        assert 'mkdir -p "/archive"' in text
        assert 'ollama rm "old"' in text  # blobs are shared; never mv them
        assert "DRY RUN ONLY" in text and "deleted" in text

    def test_move_plan_has_mv_for_cache_models(self):
        rules = Rules()
        rules.archive_dir = "/archive"
        plan = build_plan(
            [make_model("models--x", 10, 200, source="cache:hub")], rules, "move"
        )
        text = "\n".join(plan)
        assert 'mv "/fake/models--x" "/archive/models--x"' in text

    def test_delete_plan_has_rm_and_ollama_rm(self):
        rules = Rules()
        models = [
            make_model("old-ollama", 10, 200, source="ollama"),
            make_model("old-cache", 10, 200, source="cache:hub"),
        ]
        plan = build_plan(models, rules, "delete")
        text = "\n".join(plan)
        assert 'ollama rm "old-ollama"' in text
        assert 'rm -rf "/fake/old-cache"' in text
        assert "DRY RUN ONLY" in text
        assert "blobs are shared" in text

    def test_no_stale_models(self):
        rules = Rules()
        plan = build_plan([make_model("fresh", 1, 2)], rules, "move")
        joined = "\n".join(plan)
        assert "Nothing to do" in joined

    def test_bad_action_raises(self):
        with pytest.raises(ValueError, match="unknown action"):
            build_plan([], Rules(), "nuke")

    def test_steps_sorted_biggest_first(self):
        models = [make_model("small", 1, 300), make_model("big", 20, 300)]
        rules = Rules()
        joined = "\n".join(build_plan(models, rules, "delete"))
        assert joined.index("big") < joined.index("small")


class TestNeverTouchesFiles:
    def test_plan_actions_are_strings_only(self, tmp_path):
        """Building a plan must not remove or move any real files."""
        victim = tmp_path / "model-dir"
        victim.mkdir()
        (victim / "weights.bin").write_bytes(b"\x00" * 10)
        before = sorted(p.name for p in tmp_path.iterdir())
        rules = Rules()
        plan = attach_estimates(
            build_plan([make_model("x", 5, 400)], rules, "move"), [], rules
        )
        assert plan  # we got a plan back
        after = sorted(p.name for p in tmp_path.iterdir())
        assert before == after
