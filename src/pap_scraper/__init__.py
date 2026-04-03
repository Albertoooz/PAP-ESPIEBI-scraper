"""PAP ESPI/EBI report scraper (espiebi.pap.pl).

Import from the package root (`from pap_scraper import …`); symbols below form the
stable public API. Internal details stay in submodules.
"""

from __future__ import annotations

import importlib.metadata

from pap_scraper.config import Settings, load_settings
from pap_scraper.extract import find_attachment_urls
from pap_scraper.filter_entries import (
    ListEntry,
    apply_list_filters,
    effective_date_lower,
    entry_published_date,
    filter_entries,
)
from pap_scraper.list_scrape import parse_last_page_index, parse_list_page
from pap_scraper.logging_setup import setup_logging
from pap_scraper.metadata_extract import (
    node_metadata_json_path,
    parse_node_metadata,
    write_node_metadata,
)
from pap_scraper.pipeline import (
    collect_raw_list_entries,
    discover_filtered,
    fetch_last_listing_page_index,
    load_nodes_file,
    run_download_for_nodes,
    run_download_from_file,
    run_full,
    save_nodes_file,
)
from pap_scraper.storage import ManifestEntry, iter_manifest_entries, load_manifest

try:
    __version__ = importlib.metadata.version("pap-scraper")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "__version__",
    "ManifestEntry",
    "Settings",
    "ListEntry",
    "apply_list_filters",
    "collect_raw_list_entries",
    "discover_filtered",
    "effective_date_lower",
    "entry_published_date",
    "fetch_last_listing_page_index",
    "filter_entries",
    "find_attachment_urls",
    "iter_manifest_entries",
    "load_manifest",
    "load_nodes_file",
    "load_settings",
    "node_metadata_json_path",
    "parse_last_page_index",
    "parse_list_page",
    "parse_node_metadata",
    "run_download_for_nodes",
    "run_download_from_file",
    "run_full",
    "save_nodes_file",
    "setup_logging",
    "write_node_metadata",
]
