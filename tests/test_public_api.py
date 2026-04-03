"""Stable API exported from the top-level package."""

import pap_scraper


def test_version_is_non_empty_string() -> None:
    assert isinstance(pap_scraper.__version__, str)
    assert len(pap_scraper.__version__) >= 3


def test_all_exports_importable() -> None:
    for name in pap_scraper.__all__:
        assert hasattr(pap_scraper, name), f"missing export: {name}"


def test_typical_library_flow_imports() -> None:
    from pap_scraper import (
        ListEntry,
        Settings,
        discover_filtered,
        load_settings,
        run_download_for_nodes,
    )

    assert ListEntry.__name__ == "ListEntry"
    assert Settings.__name__ == "Settings"
    assert callable(discover_filtered)
    assert callable(load_settings)
    assert callable(run_download_for_nodes)
