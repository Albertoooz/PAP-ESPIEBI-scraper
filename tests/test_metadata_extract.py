from __future__ import annotations

from pathlib import Path

from pap_scraper.metadata_extract import (
    node_id_from_url,
    node_metadata_json_path,
    parse_node_metadata,
    write_node_metadata,
)

_SAMPLE_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta name="description" content="Short summary for meta." />
  <meta property="og:title" content="OG Title Example" />
  <title>Node Title From Drupal | Serwis Espi/Ebi</title>
</head>
<body>
  <h1 class="mainTitle">ESPI/EBI</h1>
  <span class="badge">ESPI</span>
  <h1 class="mainTitle"><span class="field--name-title">Node Title From Drupal</span></h1>
  <div class="field field--name-field-report-source field--label-above">
    <div class="field__item">ESPI</div>
  </div>
  <div class="field field--name-field-report-type field--label-above">
    <div class="field__item">Raport bieżący z plikiem</div>
  </div>
  <div class="field-body-xml-content">
    <p>First paragraph of the report body with enough characters to satisfy the minimum
    text length used for RAG extraction from espiebi node pages.</p>
    <p>Second paragraph with more <strong>detail</strong>.</p>
  </div>
  <a href="/download/attachment/123/path">file</a>
  <a href="/sites/default/files/x.zip">archive</a>
</body>
</html>
"""


def test_node_id_from_url() -> None:
    assert node_id_from_url("https://espiebi.pap.pl/node/718508") == "718508"
    assert node_id_from_url("https://example.com/other") is None


def test_node_metadata_json_path_uses_node_id() -> None:
    p = node_metadata_json_path(Path("out"), "https://espiebi.pap.pl/node/42")
    assert p == Path("out/node_metadata/42.json")


def test_parse_node_metadata_extracts_text_title_attachments() -> None:
    url = "https://espiebi.pap.pl/node/718508"
    seed = {
        "title": "Seed title",
        "published_at": "2026-04-01T12:00:00+02:00",
        "channel": "ESPI",
    }
    meta = parse_node_metadata(_SAMPLE_HTML, url, seed=seed)
    assert meta["node_url"] == url
    assert meta["title"] == "Node Title From Drupal"
    assert meta["report_source"] == "ESPI"
    assert meta["report_type"] == "Raport bieżący z plikiem"
    assert "First paragraph" in meta["text"]
    assert "Second paragraph" in meta["text"]
    assert "Codzienny Serwis" not in meta["text"]
    assert meta["channel"] == "ESPI"
    assert meta["published_at"] == seed["published_at"]
    assert meta["meta_description"] == "Short summary for meta."
    assert meta["language"] == "pl"
    assert meta["node_id"] == "718508"
    assert any("/download/attachment/123/path" in u for u in meta["attachment_urls"])
    assert any("x.zip" in u for u in meta["attachment_urls"])
    assert "scraped_at" in meta


def test_write_node_metadata_roundtrip(tmp_path: Path) -> None:
    meta = parse_node_metadata(
        _SAMPLE_HTML,
        "https://espiebi.pap.pl/node/1",
        seed={"title": "x"},
    )
    path = tmp_path / "node_metadata" / "1.json"
    write_node_metadata(path, meta)
    assert path.is_file()
    assert "First paragraph" in path.read_text(encoding="utf-8")
