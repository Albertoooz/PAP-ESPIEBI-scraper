from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from pap_scraper.config import Settings, load_settings
from pap_scraper.logging_setup import setup_logging
from pap_scraper.pipeline import (
    fetch_last_listing_page_index,
    run_download_from_file,
    run_full,
)


def _parse_csv_keywords(raw: str | None) -> tuple[str, ...] | None:
    if raw is None or not str(raw).strip():
        return None
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else None


def _apply_cli_args_to_settings(args: argparse.Namespace, settings: Settings) -> None:
    if getattr(args, "listing_page_count", None) is not None:
        settings.listing_page_count = args.listing_page_count
    if getattr(args, "page_start", None) is not None:
        settings.listing_page_start = args.page_start
    if getattr(args, "channel", None) is not None:
        settings.channel = args.channel  # type: ignore[assignment]
    inc = _parse_csv_keywords(getattr(args, "include_keywords", None))
    if inc is not None:
        settings.include_keywords = inc
    exc = _parse_csv_keywords(getattr(args, "exclude_keywords", None))
    if exc is not None:
        settings.exclude_keywords = exc
    if getattr(args, "no_keyword_filter", False):
        settings.skip_keyword_filter = True
    if getattr(args, "last_days", None) is not None:
        settings.last_days = args.last_days
        settings.date_from = None
        settings.date_to = None
    elif getattr(args, "since", None) or getattr(args, "until", None):
        if args.since:
            settings.date_from = date.fromisoformat(args.since)
        if args.until:
            settings.date_to = date.fromisoformat(args.until)
        settings.last_days = None


def _listing_filter_parents() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(
        "--max-page",
        type=int,
        default=None,
        dest="listing_page_count",
        metavar="N",
        help=("How many listing pages to fetch from --page-start (default: PAP_MAX_PAGE or 20)"),
    )
    p.add_argument(
        "--page-start",
        type=int,
        default=None,
        help="First listing page index (?page= is 0-based; default: 0 or PAP_LISTING_PAGE_START)",
    )
    p.add_argument(
        "--channel",
        choices=["all", "espi", "ebi"],
        default=None,
        help="Listing badge filter (default: all)",
    )
    p.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        default=None,
        help="Include entries with published date on or after this day (Europe/Warsaw)",
    )
    p.add_argument(
        "--until",
        metavar="YYYY-MM-DD",
        default=None,
        help="Include entries with published date on or before this day",
    )
    p.add_argument(
        "--last-days",
        type=int,
        default=None,
        metavar="N",
        help="Shorthand: keep entries from the last N calendar days (overrides --since/--until)",
    )
    p.add_argument(
        "--no-keyword-filter",
        action="store_true",
        help="Do not filter by include keywords (exclude keywords still apply)",
    )
    p.add_argument(
        "--include-keywords",
        metavar="CSV",
        default=None,
        help=(
            "Comma-separated substrings for titles (case-insensitive); "
            "replaces PAP_INCLUDE_KEYWORDS for this run"
        ),
    )
    p.add_argument(
        "--exclude-keywords",
        metavar="CSV",
        default=None,
        help="Comma-separated substrings to exclude from titles",
    )
    return p


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG logging",
    )
    common.add_argument(
        "--base-url",
        default=None,
        help="Service base URL (default: https://espiebi.pap.pl)",
    )
    common.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for files and manifest (default: ./reports)",
    )
    common.add_argument(
        "--no-metadata",
        action="store_true",
        help=("Do not store per-node JSON metadata under node_metadata/ (default: on, for RAG)"),
    )

    lf = _listing_filter_parents()

    p = argparse.ArgumentParser(
        prog="pap-scraper",
        description="ESPI/EBI report scraper (espiebi.pap.pl)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_sync_like(name: str, help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, parents=[common, lf], help=help_text)
        sp.add_argument(
            "--discover-only",
            action="store_true",
            help="Write node list (JSONL) only; do not download attachments",
        )
        sp.add_argument(
            "--nodes-out",
            type=Path,
            default=None,
            help="Optional path to write the filtered node list (JSONL)",
        )
        sp.add_argument(
            "--force",
            action="store_true",
            help="Re-download even if URL is already successful in the manifest",
        )
        return sp

    add_sync_like("sync", "Fetch listing, apply filters, open nodes in Playwright, download files")
    add_sync_like(
        "run",
        "Same as sync (deprecated name); fetch listing, filter, download",
    )

    p_disc = sub.add_parser(
        "discover",
        parents=[common, lf],
        help="Discover filtered nodes and write JSONL (same filters as sync)",
    )
    p_disc.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("discovered_nodes.jsonl"),
        help="Output JSONL file",
    )

    p_dl = sub.add_parser(
        "download",
        parents=[common],
        help="Download attachments for nodes from a JSONL file (no listing scan)",
    )
    p_dl.add_argument(
        "nodes_file",
        type=Path,
        help="JSONL file with node_url and title fields",
    )
    p_dl.add_argument(
        "--force",
        action="store_true",
        help="Ignore manifest success and download again",
    )

    sub.add_parser(
        "probe",
        parents=[common],
        help="Fetch listing page 0 and print last page index from pagination",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)

    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    settings = load_settings(
        base_url=args.base_url,
        output_dir=args.output_dir,
    )
    if getattr(args, "no_metadata", False):
        settings.fetch_metadata = False
    if args.command in ("sync", "run", "discover"):
        _apply_cli_args_to_settings(args, settings)

    if args.command in ("sync", "run"):
        return run_full(
            settings,
            discover_only=args.discover_only,
            nodes_out=args.nodes_out,
            force=args.force,
        )
    if args.command == "discover":
        return run_full(
            settings,
            discover_only=True,
            nodes_out=args.output,
            force=False,
        )
    if args.command == "download":
        return run_download_from_file(settings, args.nodes_file, force=args.force)
    if args.command == "probe":
        n = fetch_last_listing_page_index(settings)
        if n is None:
            print("Could not parse last page index from pagination HTML.", file=sys.stderr)
            return 1
        print(f"Last page index (0-based): {n}")
        print(f"Total pages: {n + 1}")
        return 0
    return 1
