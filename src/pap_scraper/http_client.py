from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pap_scraper.config import Settings


class DomainThrottler:
    """Minimum delay between requests to the same host."""

    def __init__(self, min_interval_sec: float) -> None:
        self._min = min_interval_sec
        self._last: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        if self._min <= 0:
            return
        netloc = urlparse(url).netloc or "default"
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last[netloc]
            need = self._min - elapsed
            if need > 0:
                time.sleep(need)
            self._last[netloc] = time.monotonic()


def build_session(settings: Settings) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": settings.user_agent})
    retry = Retry(
        total=settings.retry_total,
        connect=settings.retry_total,
        read=settings.retry_total,
        backoff_factor=settings.backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_text(
    session: requests.Session,
    throttler: DomainThrottler,
    settings: Settings,
    url: str,
) -> str:
    throttler.wait(url)
    timeout = (settings.request_timeout_connect, settings.request_timeout_read)
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return str(r.text)


def get_stream(
    session: requests.Session,
    throttler: DomainThrottler,
    settings: Settings,
    url: str,
) -> Any:
    throttler.wait(url)
    timeout = (settings.request_timeout_connect, settings.request_timeout_read)
    r = session.get(url, stream=True, timeout=timeout)
    return r
