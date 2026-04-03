from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from pap_scraper.filter_entries import ListEntry

_WARSAW = ZoneInfo("Europe/Warsaw")
_DAY_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})\s*$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*$")


def _parse_day_header(text: str) -> date | None:
    text = text.strip().replace("\n", " ")
    m = _DAY_RE.match(text)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _combine_published_at(day: date, time_text: str) -> datetime | None:
    m = _TIME_RE.match(time_text.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    try:
        return datetime(day.year, day.month, day.day, h, mi, tzinfo=_WARSAW)
    except ValueError:
        return None


def parse_list_page(html: str, base_url: str) -> list[ListEntry]:
    """Parse listing HTML for /?page=n (Drupal ESPI/EBI listing)."""
    soup = BeautifulSoup(html, "html.parser")
    entries: list[ListEntry] = []
    for ul in soup.select("ul.newsList"):
        h3 = ul.find_previous("h3")
        day_text = h3.get_text() if h3 else ""
        day_date = _parse_day_header(day_text) if day_text else None

        for li in ul.select("li.news"):
            a = li.select_one("a.link[href*='/node/'], a[href*='/node/']")
            if not a:
                continue
            raw_href = a.get("href")
            if not raw_href or isinstance(raw_href, list):
                continue
            href = raw_href.strip()
            if "/node/" not in href:
                continue
            title = a.get_text(strip=True)
            node_url = urljoin(base_url + "/", href)

            hours = li.select("div.hour")
            time_part = ""
            if hours:
                first = hours[0].get_text(strip=True)
                if _TIME_RE.match(first):
                    time_part = first

            badge_el = li.select_one(".badge")
            channel = badge_el.get_text(strip=True) if badge_el else ""

            entry: ListEntry = {"node_url": node_url, "title": title}
            if channel:
                entry["channel"] = channel
            if day_date and time_part:
                dt = _combine_published_at(day_date, time_part)
                if dt:
                    entry["published_at"] = dt.isoformat()
            entries.append(entry)

    return entries


def parse_last_page_index(html: str) -> int | None:
    """Parse ``?page=N`` from the \"last page\" pagination link (0-based index)."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("ul.pagination a.page-link"):
        title = str(a.get("title") or "").lower()
        href = str(a.get("href") or "")
        text = a.get_text(strip=True).lower()
        if "ostatniej" in title or text == "ostatnia":
            m = re.search(r"(?:\?|&)page=(\d+)", href)
            if m:
                return int(m.group(1))
    return None
