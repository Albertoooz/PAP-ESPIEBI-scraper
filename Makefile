# Editable installs place __editable__*.pth in site-packages; on macOS those files are often
# UF_HIDDEN and Python skips them → ModuleNotFoundError: pap_scraper. Use wheel install instead.
.PHONY: sync
sync:
	UV_NO_EDITABLE=1 uv sync

.PHONY: sync-all
sync-all:
	UV_NO_EDITABLE=1 uv sync --all-groups
