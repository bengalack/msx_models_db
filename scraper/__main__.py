"""CLI entry point: python -m scraper <command>"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import build as build_module, merge, msxorg, openmsx


def cmd_fetch_openmsx(args: argparse.Namespace) -> None:
    """Fetch and parse all openMSX machine configs, emit JSON."""
    models = openmsx.fetch_all(limit=args.limit, delay=args.delay)
    output = json.dumps(models, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
        print(f"Wrote {len(models)} models to {args.output}")
    else:
        print(output)


def cmd_fetch_msxorg(args: argparse.Namespace) -> None:
    """Fetch and parse all msx.org wiki model pages, emit JSON."""
    models = msxorg.fetch_all(limit=args.limit, delay=args.delay)
    output = json.dumps(models, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
        print(f"Wrote {len(models)} models to {args.output}")
    else:
        print(output)


def cmd_build(args: argparse.Namespace) -> None:
    """Run the full build pipeline."""
    resolutions_path = Path(args.resolutions) if args.resolutions else None
    build_module.build(
        do_fetch=args.fetch,
        resolutions_path=resolutions_path,
    )


def cmd_merge(args: argparse.Namespace) -> None:
    """Merge openMSX and msx.org datasets."""
    with open(args.openmsx, encoding="utf-8") as f:
        openmsx_data = json.load(f)
    with open(args.msxorg, encoding="utf-8") as f:
        msxorg_data = json.load(f)

    resolutions = {}
    if args.resolutions:
        resolutions = merge.load_resolutions(Path(args.resolutions))

    merged, conflicts = merge.merge_models(
        openmsx_data, msxorg_data, resolutions=resolutions,
    )

    merge.print_conflict_summary(conflicts)

    # Write merged output.
    output = json.dumps(merged, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
        print(f"Wrote {len(merged)} merged models to {args.output}")
    else:
        print(output)

    # Write conflicts file.
    if conflicts:
        conflicts_path = Path(args.conflicts or "data/conflicts.json")
        merge.save_conflicts(conflicts, conflicts_path)
        print(f"Wrote {len(conflicts)} conflicts to {conflicts_path}")
        print("Edit the 'use' field in that file, then re-run merge with --resolutions")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scraper",
        description="MSX Models DB scraper pipeline",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )

    sub = parser.add_subparsers(dest="command")

    # ── build ────────────────────────────────────────────────────────
    p_build = sub.add_parser(
        "build",
        help="Build data.js from cached data (or --fetch fresh data first)",
    )
    p_build.add_argument(
        "--fetch", action="store_true",
        help="Fetch fresh data from msx.org and openMSX GitHub before building",
    )
    p_build.add_argument(
        "--resolutions", default=None,
        help="Path to conflict resolution file",
    )
    p_build.set_defaults(func=cmd_build)

    # ── fetch-openmsx ────────────────────────────────────────────────
    p_openmsx = sub.add_parser(
        "fetch-openmsx",
        help="Fetch machine data from openMSX GitHub repository",
    )
    p_openmsx.add_argument(
        "-o", "--output", help="Output JSON file path (default: stdout)"
    )
    p_openmsx.add_argument(
        "--limit", type=int, default=None,
        help="Max number of files to fetch (for testing)",
    )
    p_openmsx.add_argument(
        "--delay", type=float, default=0.3,
        help="Delay between requests in seconds (default: 0.3)",
    )
    p_openmsx.set_defaults(func=cmd_fetch_openmsx)

    # ── fetch-msxorg ─────────────────────────────────────────────────
    p_msxorg = sub.add_parser(
        "fetch-msxorg",
        help="Fetch model data from msx.org wiki pages",
    )
    p_msxorg.add_argument(
        "-o", "--output", help="Output JSON file path (default: stdout)"
    )
    p_msxorg.add_argument(
        "--limit", type=int, default=None,
        help="Max number of model pages to fetch (for testing)",
    )
    p_msxorg.add_argument(
        "--delay", type=float, default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )
    p_msxorg.set_defaults(func=cmd_fetch_msxorg)

    # ── merge ───────────────────────────────────────────────────────
    p_merge = sub.add_parser(
        "merge",
        help="Merge openMSX and msx.org data into a single dataset",
    )
    p_merge.add_argument(
        "--openmsx", required=True,
        help="Path to openMSX raw JSON file",
    )
    p_merge.add_argument(
        "--msxorg", required=True,
        help="Path to msx.org raw JSON file",
    )
    p_merge.add_argument(
        "-o", "--output", help="Output merged JSON file path (default: stdout)"
    )
    p_merge.add_argument(
        "--conflicts", default=None,
        help="Output file for unresolved conflicts (default: data/conflicts.json)",
    )
    p_merge.add_argument(
        "--resolutions", default=None,
        help="Path to conflict resolution file (previously edited conflicts.json)",
    )
    p_merge.set_defaults(func=cmd_merge)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
