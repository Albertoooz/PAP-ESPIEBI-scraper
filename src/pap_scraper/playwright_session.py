from __future__ import annotations

import logging
import time

from playwright.sync_api import Page

from pap_scraper.config import Settings

logger = logging.getLogger(__name__)


def fetch_node_html(page: Page, url: str, settings: Settings) -> str:
    """Load a node page and return HTML after briefly waiting for attachment links."""
    last_exc: BaseException | None = None
    for attempt in range(1, settings.playwright_retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=settings.playwright_timeout_ms)
            try:
                sel = (
                    'a[href*="/download/attachment/"], '
                    'a[href*=".pdf"], a[href*=".zip"], a[href*=".xhtml"]'
                )
                page.wait_for_selector(sel, timeout=25_000)
            except Exception:
                logger.debug("Attachment selector timeout (25s) — using current DOM")
            page.wait_for_timeout(500)
            return page.content()
        except Exception as e:
            last_exc = e
            logger.warning(
                "Playwright attempt %s/%s for %s: %s",
                attempt,
                settings.playwright_retries,
                url,
                e,
            )
            time.sleep(min(2 ** (attempt - 1), 30))
    assert last_exc is not None
    raise last_exc
