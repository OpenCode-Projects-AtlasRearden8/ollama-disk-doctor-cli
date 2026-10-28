# ollama-disk-doctor

Keep a tidy local-model machine. This little Python CLI scans the directories
Ollama and OpenAI-compatible caches use to store models, lists everything by
size with a friendly bar chart, flags models untouched for months (per your
rules file), estimates reclaimable disk, and prints a **move-or-delete plan**.

It always prints steps — it never deletes or moves anything itself.

Part of the Asdale Dynamics, LLC beginner-friendly AI toolkit, and a natural
companion to the *local-ai-handbook* and *ai-model-picker-cli* projects.
Explained like a friend would: plain English, step by step, never condescending.
Learn more at <https://dylanasdale.github.io>.

## Why you'd want this

Local models pile up fast. A few Ollama pulls and you're juggling 30+ GB of
weight files you haven't touched since spring. This tool answers:

- What's on disk, and how big is each model?
- Which models haven't been touched in months (you decide what "months" means)?
- Roughly how much disk could I reclaim?
- What exact commands *would* clean this up (`ollama rm` for Ollama models,
  `mv` for cache folders) — printed, not executed?

## Install

Pure Python stdlib, offline, no API keys, no network calls. Nothing is installed
except the package itself.

```bash
pip install .            # from this folder (adds the ollama-disk-doctor command)
```

or just run it in place:

```bash
python -m ollama_disk_doctor list
```

## Usage

```bash
# Friendly report: sizes, bar chart, stale flags, reclaim estimate
ollama-disk-doctor list

# Point it somewhere else
ollama-disk-doctor list --ollama-dir ~/.ollama/models --cache-dir ~/.cache/huggingface/hub

# JSON output for scripting (--json flag on list)
ollama-disk-doctor list --json

# Print a safe plan (default: move stale models into an archive folder)
ollama-disk-doctor plan

# ...or a delete-style plan (STILL just printed, nothing runs)
ollama-disk-doctor plan --action delete

# See which directories it worries about
ollama-disk-doctor dirs
```

Useful flags (works on both commands):

| Flag | Meaning |
| --- | --- |
| `--rules FILE` | TOML rules file, see `rules.example.toml` |
| `--days N` | flag models untouched N+ days (default 90) |
| `--ollama-dir DIR` | Ollama models directory (default `~/.ollama/models`) |
| `--cache-dir DIR` | OpenAI-compatible cache dir; repeat for more |
| `--archive-dir DIR` | where "move" plans park files (default `~/.ollama-archive`) |
| `--bar-width N` | bar-chart width in characters (default 40) |

Safety by design: every plan line starts with a numbered step, is written for
you to read first, and is prefixed with a "DRY RUN ONLY" banner. Ollama models
always get `ollama rm <name>` (never raw blob surgery, since Ollama's blob store
is shared between models). The tool contains zero code that deletes, moves, or
writes to your model directories. Scanning is read-only.

## Rules file

Copy `rules.example.toml` to `rules.toml` (or pass `--rules`). Precedence:
CLI flags > rules file > built-in defaults.

```toml
stale_days = 90

[paths]
ollama_models_dir = "~/.ollama/models"
cache_dirs = ["~/.cache/huggingface/hub", "~/.cache/openai"]
archive_dir = "~/.ollama-archive"

[look]
bar_width = 40
```

## What it scans

- **Ollama** (`~/.ollama/models`): reads manifest JSON files and sums the blobs
  each model references; also reports unclaimed blobs not referenced by any
  manifest (candidates for `ollama rm` cleanup).
- **OpenAI-compatible caches**: directory-style caches such as HuggingFace hub
  caches (`~/.cache/huggingface/hub`), LM Studio, LiteLLM file caches, and
  `~/.cache/openai`. Add your own with `--cache-dir` or the rules file.

## Tests

```bash
python -m pytest
```

The test suite uses `tmp_path` fixtures to build fake Ollama stores and caches,
so nothing on your real machine is touched.

## License

MIT — Copyright (c) 2026 Asdale Dynamics, LLC. See `LICENSE`.
