from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from pap_scraper.extract import find_attachment_urls

_NODE_ID_RE = re.compile(r"/node/(\d+)")
# Listing header / site chrome — not the report title
_GENERIC_H1_TITLES = frozenset(
    {
        "espi/ebi",
        "espi",
        "ebi",
    }
)
_SITE_TITLE_SUFFIX = re.compile(
    r"\s*\|\s*serwis\s+espi\s*/\s*ebi\s*$",
    re.IGNORECASE,
)


def node_id_from_url(url: str) -> str | None:
    m = _NODE_ID_RE.search(url)
    return m.group(1) if m else None


def node_metadata_json_path(output_dir: Path, node_url: str) -> Path:
    """Path to per-node metadata JSON (under ``output_dir/node_metadata/``)."""
    nid = node_id_from_url(node_url)
    key = nid or hashlib.sha256(node_url.encode("utf-8")).hexdigest()[:24]
    return output_dir / "node_metadata" / f"{key}.json"


def parse_node_metadata(
    html: str,
    page_url: str,
    *,
    seed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Extract RAG-oriented fields from a Drupal ESPI/EBI node HTML page.

    ``seed`` typically contains ``title``, ``published_at``, ``channel`` from the listing JSONL;
    page values override when present.
    """
    seed = seed or {}
    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup, seed_title=str(seed.get("title") or "").strip())
    text = _extract_main_text(soup)
    published_at = _extract_published_iso(soup) or seed.get("published_at")
    channel = _extract_channel(soup) or seed.get("channel")
    report_source = _drupal_field_item(soup, "field-report-source")
    report_type = _drupal_field_item(soup, "field-report-type")
    meta_description = _meta_content(soup, "description")
    language = _html_lang(soup)

    attachment_urls = find_attachment_urls(html, page_url)

    record: dict[str, Any] = {
        "node_url": page_url,
        "title": title,
        "text": text,
        "published_at": published_at,
        "channel": channel,
        "attachment_urls": attachment_urls,
        "meta_description": meta_description,
        "language": language,
        "scraped_at": datetime.now(UTC).isoformat(),
    }
    nid = node_id_from_url(page_url)
    if nid:
        record["node_id"] = nid
    if report_source:
        record["report_source"] = report_source
    if report_type:
        record["report_type"] = report_type
    return record


def _extract_title(soup: BeautifulSoup, *, seed_title: str) -> str:
    """Prefer Drupal node title; avoid site chrome ``ESPI/EBI`` and generic meta titles."""
    for sel in (
        "h1 .field--name-title",
        "h1 span.field--name-title",
        "h1.mainTitle .field--name-title",
    ):
        el = soup.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if t and not _is_generic_title(t):
                return t

    tt = soup.find("title")
    if tt and tt.string:
        t = tt.string.strip()
        t = _SITE_TITLE_SUFFIX.sub("", t).strip()
        if t and not _is_generic_title(t):
            return t

    for meta in (
        soup.select_one('meta[property="og:title"]'),
        soup.select_one('meta[name="twitter:title"]'),
    ):
        if meta and meta.get("content"):
            t = str(meta["content"]).strip()
            t = _SITE_TITLE_SUFFIX.sub("", t).strip()
            if t and not _is_generic_title(t):
                return t

    for h1 in soup.find_all("h1"):
        t = h1.get_text(strip=True)
        if t and not _is_generic_title(t):
            return t

    return seed_title


def _is_generic_title(t: str) -> bool:
    return t.strip().lower() in _GENERIC_H1_TITLES


def _drupal_field_item(soup: BeautifulSoup, field_name: str) -> str | None:
    """e.g. ``field_name`` = ``field-report-source`` → class ``field--name-field-report-source``."""
    el = soup.select_one(f"div.field--name-{field_name} .field__item")
    if not el:
        return None
    text = el.get_text("\n", strip=True)
    return text if text else None


def _extract_main_text(soup: BeautifulSoup) -> str:
    """Report body: ``field-body-xml-content`` — not outer ``main`` (includes chrome)."""
    for sel in (
        "div.field-body-xml-content",
        "article.node--type-article div.node__content",
        "article.node--view-mode-full div.node__content",
        "div#block-espi-barrio-content article .node__content",
        "div.field--name-body",
        "div.field-body",
    ):
        el = soup.select_one(sel)
        if not el:
            continue
        clone = BeautifulSoup(str(el), "html.parser")
        for tag in clone(["script", "style", "nav", "footer"]):
            tag.decompose()
        for aside in clone.find_all("aside"):
            aside.decompose()
        text = clone.get_text("\n", strip=True)
        if len(text) >= 80:
            return text

    inner = soup.select_one("main.main-content#content[role='main']")
    if inner:
        clone = BeautifulSoup(str(inner), "html.parser")
        for tag in clone(["script", "style", "nav", "footer"]):
            tag.decompose()
        for hid in ("block-espi-barrio-page-title",):
            el = clone.find(id=hid)
            if el:
                el.decompose()
        ch = clone.select_one(".containerHeader")
        if ch:
            ch.decompose()
        text = clone.get_text("\n", strip=True)
        if len(text) >= 80:
            return text

    body = soup.find("body")
    if body:
        for tag in body(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()
        for hid in ("header",):
            el = body.find(id=hid)
            if el:
                el.decompose()
        text = body.get_text("\n", strip=True)
        return text
    return ""


def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
    m = soup.select_one(f'meta[name="{name}"]')
    if m and m.get("content"):
        return str(m["content"]).strip() or None
    if name == "description":
        m = soup.select_one('meta[property="og:description"]')
        if m and m.get("content"):
            return str(m["content"]).strip() or None
    return None


def _html_lang(soup: BeautifulSoup) -> str | None:
    html = soup.find("html")
    if html and html.get("lang"):
        return str(html["lang"]).strip() or None
    return None


def _extract_channel(soup: BeautifulSoup) -> str | None:
    for sel in (".badge", "span.badge", "div.badge"):
        el = soup.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if t:
                return t
    return None


def _extract_published_iso(soup: BeautifulSoup) -> str | None:
    time_el = soup.find("time")
    if time_el and time_el.get("datetime"):
        return str(time_el["datetime"]).strip() or None
    for prop in ("article:published_time", "og:updated_time"):
        m = soup.select_one(f'meta[property="{prop}"]')
        if m and m.get("content"):
            return str(m["content"]).strip() or None
    return None


def write_node_metadata(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
