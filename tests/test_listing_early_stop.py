"""Listing pagination stops when the newest day on a page is before ``since``."""

from __future__ import annotations

from datetime import date

from pap_scraper.config import Settings
from pap_scraper.filter_entries import ListEntry, effective_date_lower, entry_published_date


def test_entry_published_date_parses() -> None:
    e: ListEntry = {
        "node_url": "https://espiebi.pap.pl/node/1",
        "title": "x",
        "published_at": "2024-12-15T10:00:00+01:00",
    }
    assert entry_published_date(e) == date(2024, 12, 15)


def test_early_stop_when_max_date_on_page_before_since() -> None:
    lower = date(2025, 1, 1)
    batch: list[ListEntry] = [
        {
            "node_url": "https://espiebi.pap.pl/node/1",
            "title": "old",
            "published_at": "2024-12-01T12:00:00+01:00",
        },
    ]
    dates = [d for e in batch if (d := entry_published_date(e)) is not None]
    assert dates and max(dates) < lower


def test_no_early_stop_when_page_spans_since() -> None:
    lower = date(2025, 1, 1)
    batch: list[ListEntry] = [
        {
            "node_url": "https://espiebi.pap.pl/node/1",
            "title": "new",
            "published_at": "2025-06-01T12:00:00+02:00",
        },
    ]
    dates = [d for e in batch if (d := entry_published_date(e)) is not None]
    assert not (dates and max(dates) < lower)


def test_effective_date_lower_matches_since() -> None:
    s = Settings()
    s.date_from = date(2025, 1, 1)
    s.last_days = None
    assert effective_date_lower(s) == date(2025, 1, 1)
