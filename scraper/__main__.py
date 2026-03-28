"""CLI entry point: python -m scraper <command>"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import msxorg, openmsx


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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scraper",
        description="MSX Models DB scraper pipeline",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )

    sub = parser.add_subparsers(dest="command")

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
