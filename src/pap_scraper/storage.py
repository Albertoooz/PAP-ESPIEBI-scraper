from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ManifestEntry:
    url: str
    status: str  # success | failed | skipped
    local_path: str | None
    sha256: str | None
    error: str | None
    node_url: str | None = None


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_manifest(manifest_path: Path) -> dict[str, ManifestEntry]:
    if not manifest_path.is_file():
        return {}
    out: dict[str, ManifestEntry] = {}
    with manifest_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipped bad manifest line: %s", line[:80])
                continue
            url = data.get("url")
            if not url:
                continue
            out[url] = ManifestEntry(
                url=url,
                status=data.get("status", "unknown"),
                local_path=data.get("local_path"),
                sha256=data.get("sha256"),
                error=data.get("error"),
                node_url=data.get("node_url"),
            )
    return out


def append_manifest(manifest_path: Path, entry: ManifestEntry) -> None:
    ensure_output_dir(manifest_path.parent)
    line = json.dumps(asdict(entry), ensure_ascii=False) + "\n"
    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(line)


def iter_manifest_entries(manifest_path: Path) -> Iterator[ManifestEntry]:
    if not manifest_path.is_file():
        return
    with manifest_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            yield ManifestEntry(
                url=data["url"],
                status=data.get("status", "unknown"),
                local_path=data.get("local_path"),
                sha256=data.get("sha256"),
                error=data.get("error"),
                node_url=data.get("node_url"),
            )
