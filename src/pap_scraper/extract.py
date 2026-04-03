from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_ATTACHMENT_SUFFIXES = (".pdf", ".xhtml", ".zip")
# Drupal ESPI: files often under /download/attachment/{nid}/… with no extension in href.
_ATTACHMENT_PATH_MARKERS = ("/download/attachment/",)


def find_attachment_urls(html: str, page_url: str) -> list[str]:
    """Extract absolute URLs to files or download endpoints from a node page."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []

    def consider(href: str) -> None:
        href = href.strip()
        if not href or href.startswith("#"):
            return
        path_only = href.split("?", 1)[0]
        low = path_only.lower()
        ok = any(low.endswith(s) for s in _ATTACHMENT_SUFFIXES) or any(
            m in href for m in _ATTACHMENT_PATH_MARKERS
        )
        if not ok:
            return
        abs_url = urljoin(page_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            return
        if abs_url not in seen:
            seen.add(abs_url)
            out.append(abs_url)

    for tag in soup.find_all("a", href=True):
        consider(tag["href"])
    return out
