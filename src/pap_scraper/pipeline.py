from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from pap_scraper.config import Settings
from pap_scraper.download import download_attachment
from pap_scraper.extract import find_attachment_urls
from pap_scraper.filter_entries import (
    ListEntry,
    apply_list_filters,
    effective_date_lower,
    entry_published_date,
)
from pap_scraper.http_client import DomainThrottler, build_session, get_text
from pap_scraper.list_scrape import build_search_url, parse_last_page_index, parse_list_page
from pap_scraper.metadata_extract import (
    node_metadata_json_path,
    parse_node_metadata,
    write_node_metadata,
)
from pap_scraper.playwright_session import fetch_node_html
from pap_scraper.storage import load_manifest

logger = logging.getLogger(__name__)


def _use_site_search(settings: Settings) -> bool:
    if settings.skip_keyword_filter:
        return False
    if not settings.use_site_search_for_keywords:
        return False
    if not settings.include_keywords:
        return False
    return True


def fetch_last_listing_page_index(settings: Settings) -> int | None:
    """Return the last ``?page=`` index from the first listing page (see pagination)."""
    session = build_session(settings)
    throttler = DomainThrottler(settings.min_interval_sec)
    url = f"{settings.base_url}/?page=0"
    html = get_text(session, throttler, settings, url)
    return parse_last_page_index(html)


def collect_raw_list_entries_from_site_search(settings: Settings) -> list[ListEntry]:
    """Site search: one paginated fetch per include-keyword (dedupe); same caps as listing."""
    logger.info(
        "Site search: %s keyword(s), up to %s page index(es) each (from %s)",
        len(settings.include_keywords),
        settings.listing_page_count,
        settings.listing_page_start,
    )
    session = build_session(settings)
    throttler = DomainThrottler(settings.min_interval_sec)
    seen: set[str] = set()
    out: list[ListEntry] = []
    start = settings.listing_page_start
    end = start + settings.listing_page_count
    lower = effective_date_lower(settings)
    for kw in settings.include_keywords:
        for idx in range(start, end):
            url = build_search_url(settings.base_url, kw, idx)
            logger.info("Search (keyword %r) page index %s: %s", kw, idx, url)
            html = get_text(session, throttler, settings, url)
            batch = parse_list_page(html, settings.base_url)
            for e in batch:
                if e["node_url"] not in seen:
                    seen.add(e["node_url"])
                    out.append(e)
            logger.info(
                "Search %r page %s: %s entries (unique total: %s)",
                kw,
                idx,
                len(batch),
                len(out),
            )
            if lower is not None and batch:
                dates = [d for e in batch if (d := entry_published_date(e)) is not None]
                if dates and max(dates) < lower:
                    logger.info(
                        "Stopping search for keyword %r: page %s newest day %s is before since=%s",
                        kw,
                        idx,
                        max(dates),
                        lower,
                    )
                    break
    return out


def collect_raw_list_entries(settings: Settings) -> list[ListEntry]:
    """Fetch listing or site-search pages until cap or early-stop (see below)."""
    if _use_site_search(settings):
        return collect_raw_list_entries_from_site_search(settings)
    session = build_session(settings)
    throttler = DomainThrottler(settings.min_interval_sec)
    seen: set[str] = set()
    out: list[ListEntry] = []
    start = settings.listing_page_start
    end = start + settings.listing_page_count
    lower = effective_date_lower(settings)
    for idx in range(start, end):
        url = settings.list_url_template.format(page=idx)
        logger.info("Listing page index %s: %s", idx, url)
        html = get_text(session, throttler, settings, url)
        batch = parse_list_page(html, settings.base_url)
        for e in batch:
            if e["node_url"] not in seen:
                seen.add(e["node_url"])
                out.append(e)
        logger.info("Page index %s: %s entries (unique total: %s)", idx, len(batch), len(out))
        if lower is not None and batch:
            dates = [d for e in batch if (d := entry_published_date(e)) is not None]
            if dates and max(dates) < lower:
                logger.info(
                    "Stopping listing: page %s newest day %s is before since=%s — older pages "
                    "would not match date filter",
                    idx,
                    max(dates),
                    lower,
                )
                break
    return out


def discover_filtered(settings: Settings) -> list[ListEntry]:
    raw = collect_raw_list_entries(settings)
    filtered = apply_list_filters(raw, settings)
    logger.info(
        "After filters: %s / %s entries (channel=%s, skip_keyword_filter=%s)",
        len(filtered),
        len(raw),
        settings.channel,
        settings.skip_keyword_filter,
    )
    return filtered


def load_nodes_file(path: Path) -> list[ListEntry]:
    entries: list[ListEntry] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data: dict[str, Any] = json.loads(line)
            le: ListEntry = {
                "node_url": str(data["node_url"]),
                "title": str(data.get("title", "")),
            }
            if data.get("published_at") is not None:
                le["published_at"] = str(data["published_at"])
            if data.get("channel") is not None:
                le["channel"] = str(data["channel"])
            entries.append(le)
    return entries


def save_nodes_file(path: Path, entries: list[ListEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(dict(e), ensure_ascii=False) + "\n")
    logger.info("Wrote %s entries to %s", len(entries), path)


def run_download_for_nodes(
    settings: Settings,
    nodes: list[ListEntry],
    *,
    force: bool = False,
) -> tuple[int, int, list[tuple[str, str]]]:
    """
    For each node: Playwright → links → download.
    Returns (download_count, skipped_count, error_list).
    """
    manifest = load_manifest(settings.manifest_path)
    session = build_session(settings)
    throttler = DomainThrottler(settings.min_interval_sec)
    errors: list[tuple[str, str]] = []
    downloaded = 0
    skipped = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=settings.playwright_headless)
        try:
            context = browser.new_context(user_agent=settings.user_agent)
            page = context.new_page()
            for entry in nodes:
                node_url = entry["node_url"]
                try:
                    html = fetch_node_html(page, node_url, settings)
                except Exception as e:
                    err = f"node_html: {e}"
                    logger.error("%s — %s", node_url, err)
                    errors.append((node_url, err))
                    continue

                if settings.fetch_metadata:
                    meta_path = node_metadata_json_path(settings.output_dir, node_url)
                    if force or not meta_path.is_file():
                        try:
                            record = parse_node_metadata(html, node_url, seed=entry)
                            write_node_metadata(meta_path, record)
                            logger.info("Wrote metadata %s", meta_path.name)
                        except Exception as e:
                            logger.warning("Metadata for %s: %s", node_url, e)

                urls = find_attachment_urls(html, node_url)
                if not urls:
                    logger.warning("No PDF/XHTML/ZIP attachments on page: %s", node_url)
                    continue
                for att_url in urls:
                    if not force and att_url in manifest and manifest[att_url].status == "success":
                        skipped += 1
                        logger.info("Skipped (already in manifest): %s", att_url)
                        continue
                    res = download_attachment(
                        session,
                        throttler,
                        settings,
                        att_url,
                        node_url=node_url,
                        playwright_request=page.context.request,
                    )
                    if res.status == "success":
                        downloaded += 1
                        manifest[att_url] = res
                    else:
                        errors.append((att_url, res.error or "unknown"))
        finally:
            browser.close()

    return downloaded, skipped, errors


def run_full(
    settings: Settings,
    *,
    discover_only: bool,
    nodes_out: Path | None,
    force: bool,
) -> int:
    nodes = discover_filtered(settings)
    out_path = nodes_out
    if discover_only and out_path is None:
        out_path = Path("discovered_nodes.jsonl")
    if out_path is not None:
        save_nodes_file(out_path, nodes)
    if discover_only:
        return 0
    _, _, errs = run_download_for_nodes(settings, nodes, force=force)
    return 1 if errs else 0


def run_download_from_file(settings: Settings, nodes_path: Path, *, force: bool) -> int:
    nodes = load_nodes_file(nodes_path)
    _, _, errs = run_download_for_nodes(settings, nodes, force=force)
    return 1 if errs else 0
