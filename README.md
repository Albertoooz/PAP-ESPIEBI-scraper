# pap-espiebi-scraper — PAP ESPI/EBI scraper

A command-line tool and Python library that collects entries from the listing at [espiebi.pap.pl](https://espiebi.pap.pl/) (`?page=0` is the first page — 0-based indices), filters by **title keywords**, optional **ESPI/EBi channel**, **date range** / **last N days**, finds PDF / XHTML / ZIP links on `/node/…` pages using **Playwright (sync)**, then downloads them with **requests**, retries, and rate limiting.

**License:** MIT — see [`LICENSE`](LICENSE).

## Requirements

- Python 3.11+
- After install: Playwright browser binaries (`playwright install chromium` — see below)

## Install from PyPI

For users installing the published package (after it is on PyPI):

```bash
pip install pap-scraper
playwright install chromium
pap-scraper sync --max-page 3
```

The `playwright` package ships the Python driver; **browser binaries** must be installed separately with `playwright install` (once per machine or container).

Check [pypi.org/project/pap-scraper](https://pypi.org/project/pap-scraper/) for name availability — if taken, use another PyPI project name or a private index.

## Install from source (e.g. [uv](https://docs.astral.sh/uv/))

```bash
cd pap-espiebi-scraper
uv sync --no-editable
uv run playwright install chromium
```

Install **with** `--no-editable` if you hit import issues with editable setuptools installs. If `pap-scraper` raises `ModuleNotFoundError`, run `uv sync --no-editable` again.

## Usage

Primary command is **`sync`** (alias: `run` — same behaviour). Full pipeline: listing → filters → Playwright → downloads into `reports/`:

```bash
pap-scraper sync --max-page 3
```

Examples:

```bash
# Only ESPI badge rows from the listing, last 7 calendar days (Europe/Warsaw)
pap-scraper sync --channel espi --last-days 7 --no-keyword-filter

# Date range (inclusive), pages 0–4 of the listing
pap-scraper sync --since 2026-04-01 --until 2026-04-03 --page-start 0 --max-page 5

# How many pages exist (parses pagination from the first listing page)
pap-scraper probe
```

Discover filtered nodes only (writes `discovered_nodes.jsonl`):

```bash
pap-scraper discover --max-page 2 -o my_nodes.jsonl
```

Download using a previous node list without scanning the main listing:

```bash
pap-scraper download my_nodes.jsonl
```

Common flags: `--base-url`, `--output-dir`, `-v`, `--max-page` (number of listing pages to fetch), `--page-start`, `--channel` (`all` / `espi` / `ebi`), `--since` / `--until` (`YYYY-MM-DD`), `--last-days`, `--no-keyword-filter`.

## Python library

The `pap_scraper` package exposes a stable API from the top-level module (`import pap_scraper` / `from pap_scraper import …`). Typical entry points: `load_settings`, `Settings`, `run_full`, `discover_filtered`, `apply_list_filters`, `fetch_last_listing_page_index`, `run_download_from_file`, `run_download_for_nodes`. Listing parsing: `parse_list_page`, `parse_last_page_index`. Lower level: `filter_entries`, `find_attachment_urls`, manifest access: `load_manifest`, `ManifestEntry`. Each `ListEntry` may include `published_at` (ISO) and `channel` when produced from the live listing.

Example — filtered node list only (no file downloads):

```python
from pathlib import Path

from pap_scraper import discover_filtered, load_settings, save_nodes_file

settings = load_settings(listing_page_count=2, output_dir=Path("reports"))
nodes = discover_filtered(settings)
save_nodes_file(Path("my_nodes.jsonl"), nodes)
```

## Configuration

Environment variables with the `PAP_` prefix (e.g. in `.env` — load yourself or export in the shell):

| Variable | Description |
|----------|-------------|
| `PAP_MAX_PAGE` | Number of listing pages to fetch (`?page=` is 0-based; default 20) |
| `PAP_LISTING_PAGE_START` | First `?page=` index (default 0) |
| `PAP_OUTPUT_DIR` | Output directory (default `reports`) |
| `PAP_CHANNEL` | `all`, `espi`, or `ebi` |
| `PAP_DATE_FROM` / `PAP_DATE_TO` | Inclusive bounds, ISO `YYYY-MM-DD` |
| `PAP_LAST_DAYS` | Last N calendar days in Europe/Warsaw (overrides date from/to when set via CLI) |
| `PAP_SKIP_KEYWORD_FILTER` | `1` to skip include-keywords filter |
| `PAP_INCLUDE_KEYWORDS` | Comma-separated, e.g. `raport,sprawozdanie,rr,srr` (Polish ESPI titles) |
| `PAP_EXCLUDE_KEYWORDS` | Exclusions in title, e.g. `mar,nwz` |
| `PAP_MIN_INTERVAL_SEC` | Minimum interval between HTTP requests to the same host |
| `PAP_PLAYWRIGHT_TIMEOUT_MS` | Playwright navigation timeout |
| `PAP_PLAYWRIGHT_HEADLESS` | `1` / `0` |

Download manifest (append-only): `reports/.manifest.jsonl`.

Some entries have empty `/download/attachment/{nid}/path` links or missing files — downloads may end as `failed` in the manifest (e.g. HTTP 404). That reflects the service behaviour, not a bug in this tool.

## Tests

```bash
uv run python -m pytest
```

## Package layout

Source: `src/pap_scraper/`.

After publishing a public Git repo, add `Repository` and `Issues` under `[project.urls]` in `pyproject.toml` (currently `Homepage` points at the PyPI project page).

## Code quality

```bash
uv sync --all-groups --no-editable
uv run pre-commit install
uv run pre-commit run --all-files
```

CI on GitHub: Ruff, mypy, pytest, secret scanning — `.github/workflows/ci.yml`.

## Publishing to PyPI

### Typical release flow

1. **Version source of truth** — the `version` field in `pyproject.toml` (some projects use *setuptools-scm* / *hatch-vcs*; here it is a manual bump).
2. **Git release** — commit the new version, tag `v0.2.0` (prefix `v` + same version as in `pyproject.toml`, without `v` in the file).
3. **CI** — [`.github/workflows/publish.yml`](.github/workflows/publish.yml) runs on `push` of tags `v*`, checks tag ↔ `pyproject.toml`, builds (`uv build`), uploads to PyPI.

**Trusted Publishing (recommended):** link the PyPI project to this GitHub repo (OIDC) in [PyPI publishing settings](https://pypi.org/manage/account/publishing/) so you do not store long-lived tokens in secrets. Docs: [trusted publishers](https://docs.pypi.org/trusted-publishers/).

**API token (simpler start):** create a token on PyPI, add `PYPI_API_TOKEN` in GitHub secrets, and swap the publish step for the variant with `password: ${{ secrets.PYPI_API_TOKEN }}` (comment in the workflow file).

### Manual upload (no CI)

```bash
uv build
# twine upload dist/*   # after configuring PyPI account / API token
```

### Release checklist

1. Set `version` in `pyproject.toml` (e.g. `0.2.0`).
2. Commit, tag: `git tag v0.2.0` and `git push origin v0.2.0`.
3. Confirm the **Publish** workflow in the Actions tab.

## Terms of service, scraping, and liability

**This is not legal advice.** In short:

- **Publishing open-source tooling on PyPI** that *may* access a public site is not automatically unlawful — but **how you use it** and **what you do with content** may be governed by law (site terms, copyright in databases, data protection, etc.).
- **The operator (e.g. PAP)** may restrict automated access, bulk downloading, or reuse beyond permitted scope. **Violating terms** can lead to account blocks, cease-and-desist letters, or civil disputes, depending on facts and jurisdiction.
- **Do not bypass technical protections** (e.g. login where required); do not overload the service: this project uses **throttling** and sensible defaults — keep using them and respect the terms.
- **Content downloaded from ESPI** (reports, filings) may be **copyrighted** or otherwise protected; **redistribution** or building a competing database is a different risk profile than personal analytical use.

**Summary:** legal risk depends mainly on **what you do with the data** and **whether you comply with terms and reasonable load**. The package is a generic tool; **compliance is the end user’s responsibility** — consult a lawyer if unsure.
