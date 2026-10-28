# ollama-disk-doctor: friendly disk usage for local AI models.
# Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed.

"""Command line interface.

Usage:
  ollama-disk-doctor list            # sizes + bar chart + stale flags (add --json)
  ollama-disk-doctor plan            # print a move-or-delete plan (nothing runs!)

Options let you point at custom directories or a rules file (rules.toml).
Pure stdlib, offline, no keys, no network. It never deletes or moves anything.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .models import ModelInfo
from .plan import build_plan, attach_estimates
from .report import render_report
from .rules import DEFAULT_ARCHIVE_DIR, Rules
from .scanner import scan_ollama, scan_openai_cache

DEFAULT_OLLAMA_DIR = "~/.ollama/models"
DEFAULT_OPENAI_CACHE_DIRS = [
    "~/.cache/huggingface/hub",
    "~/.cache/litellm/files",
    "~/.cache/lm-studio/models",
    "~/.cache/openai",
]


def build_arg_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--rules", default=argparse.SUPPRESS,
        metavar="FILE",
        help="TOML rules file (stale days, dirs). See rules.example.toml.",
    )
    common.add_argument("--days", type=int, default=argparse.SUPPRESS, metavar="N",
                        help="flag models untouched N+ days (default 90; wins over rules)")
    common.add_argument("--ollama-dir", default=argparse.SUPPRESS, metavar="DIR",
                        help="Ollama models dir (default: rules file or ~/.ollama/models)")
    common.add_argument("--cache-dir", action="append", default=argparse.SUPPRESS, metavar="DIR",
                        help="OpenAI-compatible cache dir; repeat for more "
                             "(default: rules file or common ~/.cache locations)")
    common.add_argument("--archive-dir", default=argparse.SUPPRESS, metavar="DIR",
                        help='where "move" plans should park files (default '
                             f"{DEFAULT_ARCHIVE_DIR})")
    common.add_argument("--bar-width", type=int, default=argparse.SUPPRESS, metavar="N",
                        help="bar-chart width in characters (default 40 or rules)")

    p = argparse.ArgumentParser(
        prog="ollama-disk-doctor",
        description="Friendly local-model disk doctor: sizes, staleness, and a "
        "safe move-or-delete plan. Pure stdlib, offline.",
        epilog="It scans read-only and only ever prints. Example: "
        "ollama-disk-doctor list --days 90",
        parents=[common],
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command")
    list_p = sub.add_parser("list", parents=[common],
                            help="list models by size with bars and stale flags")
    list_p.add_argument("--json", action="store_true", help="emit machine-readable JSON instead")
    plan_p = sub.add_parser("plan", parents=[common], help="print a move-or-delete plan (dry run)")
    plan_p.add_argument("--action", choices=("move", "delete"), default="move",
                        help="what the plan steps do: default and safe choice is move")
    sub.add_parser("dirs", parents=[common], help="show which directories would be scanned")
    return p


def resolve_scan_targets(args: argparse.Namespace, rules: Rules) -> tuple[str, list[str]]:
    ollama_dir = getattr(args, "ollama_dir", None) or rules.ollama_models_dir or DEFAULT_OLLAMA_DIR
    cache_from_cli = getattr(args, "cache_dir", None)
    if cache_from_cli is not None:
        cache_dirs = cache_from_cli
    elif rules.cache_dirs:
        cache_dirs = rules.cache_dirs
    else:
        cache_dirs = list(DEFAULT_OPENAI_CACHE_DIRS)
    rules.archive_dir = getattr(args, "archive_dir", None) or rules.archive_dir
    rules.stale_days = getattr(args, "days", None) or rules.stale_days
    rules.bar_width = getattr(args, "bar_width", None) or rules.bar_width
    return ollama_dir, cache_dirs


def collect(ollama_dir: str, cache_dirs: list[str]) -> list[ModelInfo]:
    models: list[ModelInfo] = []
    models.extend(scan_ollama(ollama_dir))
    for d in cache_dirs:
        models.extend(scan_openai_cache(d))
    return models


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        rules = Rules.load(getattr(args, "rules", None))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ollama_dir, cache_dirs = resolve_scan_targets(args, rules)

    if args.command == "dirs":
        print(f"Ollama models dir: {ollama_dir}")
        print("OpenAI-compatible cache dirs:")
        for d in cache_dirs:
            print(f"  - {d}")
        return 0

    found_anywhere = os.path.isdir(os.path.expanduser(ollama_dir)) or any(
        os.path.isdir(os.path.expanduser(d)) for d in cache_dirs
    )
    models = collect(ollama_dir, cache_dirs)

    if args.command == "plan":
        action = getattr(args, "action", "move")
        plan = attach_estimates(build_plan(models, rules, action), models, rules)
        print("\n".join(plan))
        if not found_anywhere and not models:
            print("(none of the scan targets exist on this machine yet - see `ollama-disk-doctor dirs`)")
        return 0

    # default (and 'list'): the friendly report with bar chart
    if args.command == "list" and args.json:
        print(render_report(models, rules, as_json=True))
        return 0
    print(render_report(models, rules, as_json=False))
    if not found_anywhere:
        print(
            "(none of the scan targets exist on this machine yet - "
            "point me somewhere with --ollama-dir / --cache-dir)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
