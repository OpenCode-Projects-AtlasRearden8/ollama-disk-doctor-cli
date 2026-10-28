# ollama-disk-doctor tests.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

import json
import time

from ollama_disk_doctor.models import ModelInfo
from ollama_disk_doctor.report import (
    bar,
    reclaimable,
    render_report,
)
from ollama_disk_doctor.rules import Rules


def make_model(name, mb, age_days, source="ollama"):
    return ModelInfo(
        name=name,
        source=source,
        path=f"/fake/{name}",
        size_bytes=mb * 1024 * 1024,
        last_modified=time.time() - age_days * 86400,
    )


class TestReclaimable:
    def test_only_stale_counted(self):
        models = [make_model("old", 10, 200), make_model("new", 5, 3)]
        assert reclaimable(models, 90) == 10 * 1024 * 1024


class TestBar:
    def test_proportional(self):
        full = bar(1000, 1000, 10)
        half = bar(500, 1000, 10)
        assert len(full) == 10
        assert len(half) == 5

    def test_nonzero_min_one(self):
        assert len(bar(1, 1_000_000, 40)) == 1

    def test_zero_empty(self):
        assert bar(0, 100, 10) == ""


class TestRenderReport:
    def test_flags_stale_and_sizes(self):
        rules = Rules()
        text = render_report([make_model("newer", 8, 5), make_model("older", 12, 200)], rules)
        assert "newer" in text and "older" in text
        assert "*STALE*" in text
        assert "Reclaimable estimate" in text
        assert "█" in text

    def test_json_parseable(self):
        rules = Rules()
        payload = json.loads(
            render_report([make_model("j", 4, 100)], rules, as_json=True)
        )
        assert payload["stale_days"] == 90
        assert payload["models"][0]["name"] == "j"
        assert "reclaimable_bytes" in payload

    def test_empty_report_is_friendly(self):
        text = render_report([], Rules())
        assert "No models found" in text


class TestAgeFormat:
    def test_render_report_age_column(self):
        text = render_report([make_model("m", 1, 3)], Rules())
        assert "3d" in text
