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
    from .openmsx_source import FallbackXMLSource, LiveXMLSource, MirrorXMLSource
    from .slotmap import load_sha1_index
    from .slotmap_lut import load_slotmap_lut
    import requests as _requests

    lut_rules = load_slotmap_lut(build_module.SLOTMAP_LUT_PATH)
    sha1_index = load_sha1_index(
        build_module.SHA1_INDEX_PATH if build_module.SHA1_INDEX_PATH.exists() else None
    )
    sr_root = build_module.SYSTEMROMS_ROOT if build_module.SYSTEMROMS_ROOT.exists() else None

    mirror_path = Path(args.openmsx_mirror) if args.openmsx_mirror else None
    if mirror_path is None:
        cfg = build_module.load_scraper_config()
        raw = cfg.get("openmsx_mirror")
        if raw:
            mirror_path = Path(raw)
    if mirror_path is not None and args.local_openmsx_only:
        source = MirrorXMLSource(mirror_path)
        delay = 0.0
    elif mirror_path is not None:
        session = _requests.Session()
        session.headers["User-Agent"] = "msxmodelsdb-scraper/1.0"
        source = FallbackXMLSource(LiveXMLSource(session), MirrorXMLSource(mirror_path))
        delay = args.delay
    else:
        source = None
        delay = args.delay

    models = openmsx.fetch_all(
        source=source,
        limit=args.limit,
        delay=delay,
        lut_rules=lut_rules,
        sha1_index=sha1_index or None,
        systemroms_root=sr_root,
    )
    output = json.dumps(models, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
        print(f"Wrote {len(models)} models to {args.output}")
    else:
        print(output)


def cmd_fetch_msxorg(args: argparse.Namespace) -> None:
    """Fetch and parse all msx.org wiki model pages, emit JSON."""
    from .mirror import FallbackPageSource, LivePageSource, MirrorPageSource
    import requests as _requests
    mirror_path = Path(args.msxorg_mirror) if args.msxorg_mirror else None
    if mirror_path is None:
        cfg = build_module.load_scraper_config()
        raw = cfg.get("msxorg_mirror")
        if raw:
            mirror_path = Path(raw)
    if mirror_path is not None and args.local_msxorg_only:
        source = MirrorPageSource(mirror_path)
        delay = 0.0
    elif mirror_path is not None:
        session = _requests.Session()
        session.headers["User-Agent"] = "msxmodelsdb-scraper/1.0"
        source = FallbackPageSource(LivePageSource(session), MirrorPageSource(mirror_path))
        delay = args.delay
    else:
        source = None
        delay = args.delay
    models = msxorg.fetch_all(source=source, limit=args.limit, delay=delay)
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
    openmsx_mirror_path = Path(args.openmsx_mirror) if args.openmsx_mirror else None
    mirror_path = Path(args.msxorg_mirror) if args.msxorg_mirror else None
    build_module.build(
        do_fetch=args.fetch,
        resolutions_path=resolutions_path,
        openmsx_mirror_path=openmsx_mirror_path,
        local_openmsx_only=args.local_only or args.local_openmsx_only,
        mirror_path=mirror_path,
        local_only=args.local_only or args.local_msxorg_only,
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
    # Ensure stdout/stderr can handle Unicode (slotmap uses ⌧, ⌴ etc.)
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

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
    p_build.add_argument(
        "--msxorg-mirror", default=None, metavar="DIR",
        help="Local directory of browser-saved msx.org HTML files."
             " Overrides msxorg_mirror in scraper-config.json."
             " Default mode: try live first, use mirror on failure.",
    )
    p_build.add_argument(
        "-l", "--local-only", action="store_true",
        help="Skip all live requests; use local mirror files for both msx.org and openMSX."
             " Shorthand for --local-msxorg-only --local-openmsx-only.",
    )
    p_build.add_argument(
        "--local-msxorg-only", action="store_true",
        help="Skip live msx.org requests entirely; use mirror files only."
             " Requires --msxorg-mirror or msxorg_mirror in scraper-config.json.",
    )
    p_build.add_argument(
        "--openmsx-mirror", default=None, metavar="DIR",
        help="Local directory of openMSX machine XML files (e.g. share/machines)."
             " Overrides openmsx_mirror in scraper-config.json."
             " Default mode: try GitHub first, use mirror on failure.",
    )
    p_build.add_argument(
        "--local-openmsx-only", action="store_true",
        help="Skip live GitHub requests for openMSX data entirely; use mirror files only."
             " Requires --openmsx-mirror or openmsx_mirror in scraper-config.json.",
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
    p_openmsx.add_argument(
        "--openmsx-mirror", default=None, metavar="DIR",
        help="Local directory of openMSX machine XML files (e.g. share/machines)."
             " Default mode: try GitHub first, use mirror on failure.",
    )
    p_openmsx.add_argument(
        "-l", "--local-openmsx-only", action="store_true",
        help="Skip live GitHub requests entirely; use mirror files only.",
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
    p_msxorg.add_argument(
        "--msxorg-mirror", default=None, metavar="DIR",
        help="Local directory of browser-saved msx.org HTML files."
             " Default mode: try live first, use mirror on failure.",
    )
    p_msxorg.add_argument(
        "-l", "--local-msxorg-only", action="store_true",
        help="Skip live msx.org requests entirely; use mirror files only.",
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
