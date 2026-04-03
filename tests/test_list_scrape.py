from pap_scraper.list_scrape import parse_last_page_index, parse_list_page

_HTML = """
<section class="region-page-listing">
<div class="view view-report-listing">
  <div class="day">
  <h3>03.04.2026</h3>
  <ul class="newsList">
    <li class="news">
      <div class="badge">ESPI</div>
      <div class="hour">17:15</div>
      <div class="hour">3/2026</div>
      <a class="link" href="/node/111">ACME - Annual report</a>
    </li>
    <li class="news">
      <div class="badge">EBi</div>
      <div class="hour">16:00</div>
      <div class="hour">1/2026</div>
      <a class="link" href="/node/222">OTHER - Notice</a>
    </li>
  </ul>
  </div>
</div>
</section>
"""


def test_parse_list_page_structure() -> None:
    base = "https://espiebi.pap.pl"
    entries = parse_list_page(_HTML, base)
    assert len(entries) == 2
    by_url = {e["node_url"]: e for e in entries}
    assert by_url[f"{base}/node/111"]["channel"] == "ESPI"
    assert by_url[f"{base}/node/222"]["channel"] == "EBi"
    assert "published_at" in by_url[f"{base}/node/111"]
    assert by_url[f"{base}/node/111"]["title"].startswith("ACME")


def test_parse_list_page_minimal_legacy() -> None:
    """Older HTML shape: link only (still works)."""
    html = '<ul class="newsList"><li class="news"><a href="/node/1">X</a></li></ul>'
    entries = parse_list_page(html, "https://espiebi.pap.pl")
    assert len(entries) == 1
    assert entries[0]["node_url"].endswith("/node/1")


def test_find_attachment_urls() -> None:
    from pap_scraper.extract import find_attachment_urls

    h = '<html><body><a href="/sites/default/files/x.pdf">x</a></body></html>'
    urls = find_attachment_urls(h, "https://espiebi.pap.pl/node/1")
    assert urls[0].endswith(".pdf")


def test_find_download_attachment_path() -> None:
    from pap_scraper.extract import find_attachment_urls

    h = '<a href="/download/attachment/123/path">file</a>'
    urls = find_attachment_urls(h, "https://espiebi.pap.pl/node/123")
    assert "/download/attachment/123/path" in urls[0]


def test_parse_last_page_index() -> None:
    html = """
    <nav><ul class="pagination js-pager__items">
      <li><a href="?page=1" class="page-link">2</a></li>
      <li><a href="?page=23831" title="Przejdź do ostatniej strony" class="page-link">
        <span>Ostatnia</span></a></li>
    </ul></nav>
    """
    assert parse_last_page_index(html) == 23831
