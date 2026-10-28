# STATUS.md — ollama-disk-doctor

## What was built

`ollama-disk-doctor` — a pure-stdlib Python CLI that keeps a local-model machine
tidy. It scans Ollama model stores and OpenAI-compatible/HuggingFace-style
cache directories, lists models by size with a friendly ASCII bar chart, flags
models untouched for months (threshold from a TOML rules file or `--days`),
estimates reclaimable disk, and prints a move-or-delete plan made of individual
readable steps. It never executes a step itself: no delete, no move, no write
to your model directories — scanning is read-only and the plan is dry-run text
with a "DRY RUN ONLY" banner. For Ollama-managed models the plan prints
`ollama rm <name>` (Ollama's blob store is shared between models, so raw blob
surgery is never suggested).

Structure:
- `ollama_disk_doctor/scanner.py` — read-only scanning: Ollama manifest JSON +
  blob size summation, unclaimed-blob detection, cache-directory grouping;
  `human_size()` formatting.
- `ollama_disk_doctor/rules.py` — TOML rules (`tomllib`): `stale_days`,
  `paths.ollama_models_dir`, `paths.cache_dirs`, `paths.archive_dir`,
  `look.bar_width`. Precedence: CLI flags > rules file > defaults.
- `ollama_disk_doctor/report.py` — sorted listing, proportional `█` bars,
  stale flags, reclaim estimate, and `--json` output.
- `ollama_disk_doctor/plan.py` — numbered move-or-delete plan (strings only).
- `ollama_disk_doctor/cli.py` — argparse CLI (`list`, `plan`, `dirs`,
  `--json`, `--days`, `--rules`, `--ollama-dir`, `--cache-dir`, `--archive-dir`,
  `--bar-width`); shared flags work before or after the subcommand.
- `rules.example.toml` — documented rules example.
- `tests/` — pytest suite with tmp-path fixtures (44 tests).
- `README.md`, `LICENSE` (MIT, Copyright (c) 2026 Asdale Dynamics, LLC),
  `pyproject.toml` (console script entry point), `.gitignore`.

## How to run it

```bash
pip install .                      # adds the `ollama-disk-doctor` command
ollama-disk-doctor list            # friendly report with bars + stale flags
ollama-disk-doctor list --json     # JSON for scripting
ollama-disk-doctor plan            # printed move plan (dry run, default: move)
ollama-disk-doctor plan --action delete   # printed delete plan (still dry)
ollama-disk-doctor dirs            # show scan targets
python -m ollama_disk_doctor list  # also works without installing
```

Point at custom locations with `--ollama-dir`, repeatable `--cache-dir`,
and `--rules rules.toml` (copy from `rules.example.toml`; `–days N` overrides
the stale threshold).

## Verification results

- `python3 -m pytest -q` → **44 passed** (tests use tmp-path fixtures; the
  real machine's model dirs are never touched).
- `python3 -m compileall ollama_disk_doctor tests` → OK.
- `pip install -e .` and `pip wheel . ` → wheel
  `ollama_disk_doctor-0.1.0-py3-none-any.whl` builds cleanly; console script
  installs and `ollama-disk-doctor --version` → `0.1.0`.
- End-to-end run against synthetic fixtures (5 GiB 230-day-old Ollama model,
  700 MiB fresh Ollama model, 2 GiB 150-day-old HuggingFace-style cache entry):
  - `list`: bar chart correct, 2 stale flagged, "Reclaimable estimate: 8.0 GiB".
  - `plan` (move): step 1 `mkdir -p "<archive>"`, then `ollama rm` for the
    Ollama model, `mv` for the cache folder, verification reminder.
  - `plan --action delete`: `ollama rm` / `rm -rf` steps plus a
    shared-blobs warning tip.
  - `list --json`: valid JSON with totals, reclaim estimate, and per-model
    records.
  - Empty machine: friendly "No models found" message.
- Nothing in the plan module imports shutil or executes shell commands; a test
  asserts that building a plan leaves a tmp directory untouched.

## Known gaps

- Sizes come from filesystem metadata (manifest-declared blob sizes, or actual
  file sizes for caches). Hardlinks are counted per-file (could slightly
  double-count shared files in some cache layouts).
- Ollama manifest discovery assumes the standard `manifests/<registry>/<...>`
  layout; exotic registries with unusual nesting still produce a best-effort
  name.
- Cache scan is generic (group by top-level directory), so highly fragmented
  caches may show a single large group rather than per-model entries.
- No `--write-plan FILE` option yet (copy/paste from the terminal works).
- Only English output; no color/TTY detection keeps the output copy-paste safe.
- Not yet tested against caches from tools like vLLM-specific layouts —
  point it at those with `--cache-dir`.
