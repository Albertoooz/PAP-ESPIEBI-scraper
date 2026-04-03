from pap_scraper.config import Settings, load_settings
from pap_scraper.filter_entries import ListEntry, apply_list_filters, filter_entries


def test_include_raport() -> None:
    entries: list[ListEntry] = [
        {"node_url": "https://espiebi.pap.pl/node/1", "title": "FOO - Current raport no. 1"},
        {"node_url": "https://espiebi.pap.pl/node/2", "title": "BAR - MAR notification"},
    ]
    out = filter_entries(entries, ("raport",), ())
    assert len(out) == 1
    assert out[0]["node_url"].endswith("/node/1")


def test_exclude() -> None:
    entries: list[ListEntry] = [
        {"node_url": "https://x/node/1", "title": "Raport regarding MAR"},
    ]
    out = filter_entries(entries, ("raport",), ("mar",))
    assert len(out) == 0


def test_short_keyword_rr_word_boundary() -> None:
    entries: list[ListEntry] = [
        {"node_url": "https://x/node/1", "title": "FOO - RR for 2025"},
        {"node_url": "https://x/node/2", "title": "Consolidated report without abbreviation"},
    ]
    out = filter_entries(entries, ("rr",), ())
    assert len(out) == 1
    assert "/node/1" in out[0]["node_url"]


def test_filter_by_channel_espi() -> None:
    entries: list[ListEntry] = [
        {"node_url": "https://x/a", "title": "A", "channel": "ESPI"},
        {"node_url": "https://x/b", "title": "B", "channel": "EBi"},
    ]
    s = load_settings(channel="espi", skip_keyword_filter=True)
    out = apply_list_filters(entries, s)
    assert len(out) == 1
    assert out[0]["node_url"].endswith("/a")


def test_skip_keyword_filter() -> None:
    entries: list[ListEntry] = [
        {"node_url": "https://x/a", "title": "No keyword match here"},
    ]
    s = Settings()
    s.skip_keyword_filter = True
    s.include_keywords = ("nope",)
    s.exclude_keywords = ()
    out = apply_list_filters(entries, s)
    assert len(out) == 1
