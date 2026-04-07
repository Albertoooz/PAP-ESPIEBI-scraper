# Publishing to PyPI

## Typical release flow

1. **Version source of truth** — the `version` field in `pyproject.toml` (some projects use *setuptools-scm* / *hatch-vcs*; here it is a manual bump).
2. **Commit** the version bump to `main` (or your release branch).
3. **Publish** — in GitHub: **Actions** → **Publish** → **Run workflow** (manual only). The workflow reads the version from `pyproject.toml` on the selected branch, runs `uv build`, and uploads to PyPI. Optional: tag `v0.2.0` in git for visibility; publishing does not require a tag.

**Trusted Publishing (recommended):** link the PyPI project to this GitHub repo (OIDC) in [PyPI publishing settings](https://pypi.org/manage/account/publishing/) so you do not store long-lived tokens in secrets. Docs: [trusted publishers](https://docs.pypi.org/trusted-publishers/).

**API token (simpler start):** create a token on PyPI, add `PYPI_API_TOKEN` in GitHub secrets, and swap the publish step for the variant with `password: ${{ secrets.PYPI_API_TOKEN }}` (comment in the workflow file).

## Manual upload (no CI)

```bash
uv build
# twine upload dist/*   # after configuring PyPI account / API token
```

## Release checklist

1. Set `version` in `pyproject.toml` (e.g. `0.2.0`).
2. Commit and push to the branch you will select when running the workflow (usually `main`).
3. **Actions** → **Publish** → **Run workflow** → choose branch → **Run workflow**.
