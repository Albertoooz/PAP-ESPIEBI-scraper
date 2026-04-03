from __future__ import annotations

import hashlib
import io
import logging
import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import requests

from pap_scraper.config import Settings
from pap_scraper.http_client import DomainThrottler, get_stream
from pap_scraper.storage import ManifestEntry, append_manifest

if TYPE_CHECKING:
    from playwright.sync_api import APIRequestContext

logger = logging.getLogger(__name__)


def _normalize_headers(h: object) -> dict[str, str]:
    if hasattr(h, "items"):
        return {str(k).lower(): str(v) for k, v in h.items()}  # type: ignore[union-attr]
    return {}


def _filename_from_disposition(url: str, headers: dict[str, str], data: bytes) -> tuple[str, bool]:
    """Return (filename, is_zip)."""
    cd = headers.get("content-disposition", "")
    for pattern in (
        r"filename\*=UTF-8''([^;\n]+)",
        r'filename="([^"]+)"',
        r"filename=([^;\n]+)",
    ):
        m = re.search(pattern, cd, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().strip('"')
            if "''" in raw and "UTF-8" in cd:
                raw = raw.split("''", 1)[-1]
            name = Path(raw).name
            if name:
                return name, name.lower().endswith(".zip")

    ct = headers.get("content-type", "").lower()
    tail = url.rstrip("/").split("/")[-1].split("?")[0]
    if tail in ("path", "attachment", "download", "") or not tail:
        if "zip" in ct or data[:4] == b"PK\x03\x04":
            return "document.zip", True
        if "pdf" in ct or data[:4] == b"%PDF":
            return "document.pdf", False
        if "html" in ct:
            return "document.html", False
        return "document.bin", False
    is_zip = tail.lower().endswith(".zip")
    return tail, is_zip


def _unique_file_path(dir_path: Path, filename: str) -> Path:
    p = dir_path / filename
    if not p.exists():
        return p
    stem = Path(filename).stem
    suf = Path(filename).suffix
    for i in range(1, 10_000):
        cand = dir_path / f"{stem}_{i}{suf}"
        if not cand.exists():
            return cand
    raise OSError(f"Could not find an unused filename for {filename}")


def _unique_dir_path(parent: Path, name: str) -> Path:
    p = parent / name
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        return p
    for i in range(1, 10_000):
        q = parent / f"{name}_{i}"
        if not q.exists():
            q.mkdir(parents=True, exist_ok=True)
            return q
    raise OSError(f"Could not create directory for {name}")


def _extract_zip_bytes(data: bytes, dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(dest)
        return zf.namelist()


def _load_bytes(
    session: requests.Session,
    throttler: DomainThrottler,
    settings: Settings,
    url: str,
    playwright_request: APIRequestContext | None,
) -> tuple[bytes, dict[str, str]]:
    if playwright_request is not None:
        throttler.wait(url)
        timeout_ms = int((settings.request_timeout_connect + settings.request_timeout_read) * 1000)
        r = playwright_request.get(url, timeout=timeout_ms)
        headers = _normalize_headers(r.headers)
        if r.status != 200:
            raise requests.HTTPError(f"HTTP {r.status}")
        return r.body(), headers

    resp = get_stream(session, throttler, settings, url)
    try:
        if resp.status_code == 404:
            raise requests.HTTPError("HTTP 404")
        resp.raise_for_status()
    except requests.RequestException:
        raise
    return resp.content, _normalize_headers(resp.headers)


def download_attachment(
    session: requests.Session,
    throttler: DomainThrottler,
    settings: Settings,
    url: str,
    *,
    node_url: str | None,
    playwright_request: APIRequestContext | None = None,
) -> ManifestEntry:
    dest_dir = settings.output_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        data, headers = _load_bytes(session, throttler, settings, url, playwright_request)
    except requests.HTTPError as e:
        err = str(e)
        entry = ManifestEntry(
            url=url,
            status="failed",
            local_path=None,
            sha256=None,
            error=err,
            node_url=node_url,
        )
        append_manifest(settings.manifest_path, entry)
        return entry
    except requests.RequestException as e:
        entry = ManifestEntry(
            url=url,
            status="failed",
            local_path=None,
            sha256=None,
            error=str(e),
            node_url=node_url,
        )
        append_manifest(settings.manifest_path, entry)
        return entry
    except Exception as e:
        entry = ManifestEntry(
            url=url,
            status="failed",
            local_path=None,
            sha256=None,
            error=str(e),
            node_url=node_url,
        )
        append_manifest(settings.manifest_path, entry)
        return entry

    digest = hashlib.sha256(data).hexdigest()
    filename, is_zip = _filename_from_disposition(url, headers, data)
    lower = filename.lower()
    if not is_zip and lower.endswith(".zip"):
        is_zip = True

    if is_zip or lower.endswith(".zip"):
        stem = Path(filename).stem or "archive"
        try:
            extract_root = _unique_dir_path(dest_dir, stem)
            names = _extract_zip_bytes(data, extract_root)
            logger.info("Extracted ZIP to %s (%s files)", extract_root, len(names))
            entry = ManifestEntry(
                url=url,
                status="success",
                local_path=str(extract_root),
                sha256=digest,
                error=None,
                node_url=node_url,
            )
        except zipfile.BadZipFile as e:
            zip_name = filename if filename.endswith(".zip") else f"{filename}.zip"
            raw = _unique_file_path(dest_dir, zip_name)
            raw.write_bytes(data)
            logger.warning("Corrupt ZIP, saved raw file: %s — %s", raw, e)
            entry = ManifestEntry(
                url=url,
                status="success",
                local_path=str(raw),
                sha256=digest,
                error=f"bad_zip_saved_raw: {e}",
                node_url=node_url,
            )
        append_manifest(settings.manifest_path, entry)
        return entry

    file_path = _unique_file_path(dest_dir, filename)
    file_path.write_bytes(data)
    entry = ManifestEntry(
        url=url,
        status="success",
        local_path=str(file_path),
        sha256=digest,
        error=None,
        node_url=node_url,
    )
    append_manifest(settings.manifest_path, entry)
    logger.info("Saved %s", file_path)
    return entry
