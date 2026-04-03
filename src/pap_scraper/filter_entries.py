from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import NotRequired, TypedDict
from zoneinfo import ZoneInfo

from pap_scraper.config import Settings

logger = logging.getLogger(__name__)

_WARSAW = ZoneInfo("Europe/Warsaw")


class ListEntry(TypedDict):
    node_url: str
    title: str
    published_at: NotRequired[str]
    channel: NotRequired[str]


def _wordish_match(title_lower: str, keyword: str) -> bool:
    """Match: substring for phrases; short tokens (rr, srr) use word boundaries."""
    kw = keyword.lower().strip()
    if len(kw) <= 3 and re.fullmatch(r"[a-ząćęłńóśźż0-9]+", kw):
        return bool(re.search(rf"\b{re.escape(kw)}\b", title_lower))
    return kw in title_lower


def filter_entries(
    entries: list[ListEntry],
    include_keywords: tuple[str, ...],
    exclude_keywords: tuple[str, ...],
) -> list[ListEntry]:
    """Keyword include/exclude only (legacy helper)."""
    if not include_keywords:
        logger.warning("include_keywords is empty — returning no entries (safe default).")
        return []
    out: list[ListEntry] = []
    for e in entries:
        title_lower = e["title"].lower()
        if not any(_wordish_match(title_lower, inc) for inc in include_keywords):
            continue
        if exclude_keywords and any(ex.lower() in title_lower for ex in exclude_keywords):
            continue
        out.append(e)
    return out


def entry_published_date(entry: ListEntry) -> date | None:
    """Calendar date (Europe/Warsaw) from ``published_at``, or None if missing/invalid."""
    raw = entry.get("published_at")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_WARSAW)
        return dt.astimezone(_WARSAW).date()
    except ValueError:
        return None


def effective_date_lower(settings: Settings) -> date | None:
    """Lower calendar date for filters and listing early-stop (same as date filter lower bound)."""
    today = datetime.now(_WARSAW).date()
    if settings.last_days is not None:
        return today - timedelta(days=settings.last_days - 1) if settings.last_days > 0 else today
    return settings.date_from


def _normalize_channel_badge(raw: str) -> str:
    t = raw.strip().upper()
    if "ESPI" in t and "EBI" not in t.replace("ESPI", ""):
        return "espi"
    if "EBI" in t:
        return "ebi"
    return t.lower()


def filter_by_channel(entries: list[ListEntry], channel: str) -> list[ListEntry]:
    if channel == "all":
        return list(entries)
    out: list[ListEntry] = []
    for e in entries:
        badge = e.get("channel", "").strip()
        if not badge:
            continue
        got = _normalize_channel_badge(badge)
        if channel == "espi" and got == "espi":
            out.append(e)
        elif channel == "ebi" and got == "ebi":
            out.append(e)
    return out


def filter_by_date_settings(entries: list[ListEntry], settings: Settings) -> list[ListEntry]:
    """Filter by ``date_from``, ``date_to``, ``last_days`` (Warsaw calendar dates)."""
    today = datetime.now(_WARSAW).date()
    lower: date | None = settings.date_from
    upper: date | None = settings.date_to
    if settings.last_days is not None:
        lower = today - timedelta(days=settings.last_days - 1) if settings.last_days > 0 else today
        upper = today

    if lower is None and upper is None:
        return list(entries)

    dropped = 0
    out: list[ListEntry] = []
    for e in entries:
        d = entry_published_date(e)
        if d is None:
            dropped += 1
            continue
        if lower is not None and d < lower:
            continue
        if upper is not None and d > upper:
            continue
        out.append(e)
    if dropped:
        logger.warning(
            "Dropped %s entries without published_at under active date filter",
            dropped,
        )
    return out


def filter_by_keywords_settings(entries: list[ListEntry], settings: Settings) -> list[ListEntry]:
    """Apply include/exclude keywords; if ``skip_keyword_filter``, only exclude."""
    if settings.skip_keyword_filter:
        out: list[ListEntry] = []
        for e in entries:
            title_lower = e["title"].lower()
            if settings.exclude_keywords and any(
                ex.lower() in title_lower for ex in settings.exclude_keywords
            ):
                continue
            out.append(e)
        return out
    return filter_entries(entries, settings.include_keywords, settings.exclude_keywords)


def apply_list_filters(entries: list[ListEntry], settings: Settings) -> list[ListEntry]:
    """Channel → date → keywords (same order as typical narrowing)."""
    out = filter_by_channel(entries, settings.channel)
    out = filter_by_date_settings(out, settings)
    out = filter_by_keywords_settings(out, settings)
    return out
