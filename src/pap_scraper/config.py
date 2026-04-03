from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return default
    return int(v)


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return default
    return float(v)


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _parse_keywords_csv(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return default
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else default


def _env_date(key: str) -> date | None:
    v = os.environ.get(key)
    if not v or not v.strip():
        return None
    return date.fromisoformat(v.strip())


def _env_channel() -> Literal["all", "espi", "ebi"]:
    v = (os.environ.get("PAP_CHANNEL") or "all").strip().lower()
    if v in ("all", "espi", "ebi"):
        return v  # type: ignore[return-value]
    return "all"


@dataclass
class Settings:
    """Settings from defaults and `PAP_*` environment variables."""

    base_url: str = field(
        default_factory=lambda: _env_str("PAP_BASE_URL", "https://espiebi.pap.pl").rstrip("/")
    )
    output_dir: Path = field(default_factory=lambda: Path(_env_str("PAP_OUTPUT_DIR", "reports")))
    #: Number of listing pages to fetch (?page= is 0-based). Env: ``PAP_MAX_PAGE``.
    listing_page_count: int = field(default_factory=lambda: _env_int("PAP_MAX_PAGE", 20))
    #: First listing page index (inclusive). Env: ``PAP_LISTING_PAGE_START``.
    listing_page_start: int = field(default_factory=lambda: _env_int("PAP_LISTING_PAGE_START", 0))
    # HTTP
    request_timeout_connect: float = field(
        default_factory=lambda: _env_float("PAP_REQUEST_TIMEOUT_CONNECT", 15.0)
    )
    request_timeout_read: float = field(
        default_factory=lambda: _env_float("PAP_REQUEST_TIMEOUT_READ", 120.0)
    )
    retry_total: int = field(default_factory=lambda: _env_int("PAP_RETRY_TOTAL", 6))
    backoff_factor: float = field(default_factory=lambda: _env_float("PAP_BACKOFF_FACTOR", 1.0))
    min_interval_sec: float = field(default_factory=lambda: _env_float("PAP_MIN_INTERVAL_SEC", 0.6))
    user_agent: str = field(
        default_factory=lambda: _env_str(
            "PAP_USER_AGENT",
            "pap-scraper/0.1 (educational; +https://espiebi.pap.pl)",
        )
    )
    # Title filter keywords (Polish ESPI wording matches live listing titles)
    include_keywords: tuple[str, ...] = field(
        default_factory=lambda: _parse_keywords_csv(
            os.environ.get("PAP_INCLUDE_KEYWORDS"),
            ("raport", "sprawozdanie", "rr", "srr"),
        )
    )
    exclude_keywords: tuple[str, ...] = field(
        default_factory=lambda: _parse_keywords_csv(
            os.environ.get("PAP_EXCLUDE_KEYWORDS"),
            (),
        )
    )
    #: If True, do not require title keywords (still applies ``exclude_keywords``).
    skip_keyword_filter: bool = field(
        default_factory=lambda: _env_bool("PAP_SKIP_KEYWORD_FILTER", False),
    )
    #: ``all`` | ``espi`` | ``ebi`` — filter by listing badge.
    channel: Literal["all", "espi", "ebi"] = field(default_factory=_env_channel)
    #: Inclusive date lower bound (entry ``published_at`` date). Env: ``PAP_DATE_FROM`` (ISO).
    date_from: date | None = field(default_factory=lambda: _env_date("PAP_DATE_FROM"))
    #: Inclusive date upper bound. Env: ``PAP_DATE_TO``.
    date_to: date | None = field(default_factory=lambda: _env_date("PAP_DATE_TO"))
    #: Keep entries from the last N calendar days (Europe/Warsaw). Env: ``PAP_LAST_DAYS``.
    last_days: int | None = field(
        default_factory=lambda: (
            None
            if not (os.environ.get("PAP_LAST_DAYS") or "").strip()
            else int(os.environ["PAP_LAST_DAYS"].strip())
        )
    )
    # Playwright
    playwright_timeout_ms: int = field(
        default_factory=lambda: _env_int("PAP_PLAYWRIGHT_TIMEOUT_MS", 90_000)
    )
    playwright_retries: int = field(default_factory=lambda: _env_int("PAP_PLAYWRIGHT_RETRIES", 3))
    playwright_headless: bool = field(
        default_factory=lambda: (
            os.environ.get("PAP_PLAYWRIGHT_HEADLESS", "1").lower() not in ("0", "false", "no")
        )
    )
    #: Parse and store per-node JSON (text + fields for RAG).
    #: Env: ``PAP_FETCH_METADATA`` (0/false to disable).
    fetch_metadata: bool = field(
        default_factory=lambda: _env_bool("PAP_FETCH_METADATA", True),
    )

    @property
    def manifest_path(self) -> Path:
        return self.output_dir / ".manifest.jsonl"

    @property
    def list_url_template(self) -> str:
        return f"{self.base_url}/?page={{page}}"


def load_settings(
    *,
    base_url: str | None = None,
    output_dir: Path | None = None,
    max_page: int | None = None,
    listing_page_count: int | None = None,
    listing_page_start: int | None = None,
    include_keywords: tuple[str, ...] | None = None,
    exclude_keywords: tuple[str, ...] | None = None,
    skip_keyword_filter: bool | None = None,
    channel: Literal["all", "espi", "ebi"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    last_days: int | None = None,
    fetch_metadata: bool | None = None,
) -> Settings:
    """Load settings; ``max_page`` is a deprecated alias for ``listing_page_count``."""
    s = Settings()
    if base_url is not None:
        s.base_url = base_url.rstrip("/")
    if output_dir is not None:
        s.output_dir = output_dir
    if listing_page_count is not None:
        s.listing_page_count = listing_page_count
    elif max_page is not None:
        s.listing_page_count = max_page
    if listing_page_start is not None:
        s.listing_page_start = listing_page_start
    if include_keywords is not None:
        s.include_keywords = include_keywords
    if exclude_keywords is not None:
        s.exclude_keywords = exclude_keywords
    if skip_keyword_filter is not None:
        s.skip_keyword_filter = skip_keyword_filter
    if channel is not None:
        s.channel = channel
    if date_from is not None:
        s.date_from = date_from
    if date_to is not None:
        s.date_to = date_to
    if last_days is not None:
        s.last_days = last_days
    if fetch_metadata is not None:
        s.fetch_metadata = fetch_metadata
    return s
