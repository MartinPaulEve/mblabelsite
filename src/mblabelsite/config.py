"""Constants and configuration for mblabelsite."""

import tomllib
from pathlib import Path

_DEFAULTS = {
    "label_id": "62db3e96-423a-4e9d-bf66-7a017f1dfc73",
    "site_url": "https://ticitaci.com",
    "excluded_release_ids": ["14f0377a-dadf-4fb9-a141-4a6e8c9ed882"],
    "ignored_artist_ids": [
        "8a26ca9b-d542-449b-a5e7-224da9eb8a77",
        "89ad4ac3-39f7-470e-963a-56509c546377",
    ],
}


def _find_pyproject(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for pyproject.toml. Return Path or None."""
    if start is None:
        start = Path(__file__).resolve().parent
    current = start
    while True:
        candidate = current / "pyproject.toml"
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _load_tool_config(pyproject_path: Path | None = None) -> dict:
    """Return the [tool.mblabelsite] dict from pyproject.toml, or {} on any failure."""
    if pyproject_path is None:
        pyproject_path = _find_pyproject()
    if pyproject_path is None or not pyproject_path.is_file():
        return {}
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("tool", {}).get("mblabelsite", {})
    except Exception:
        return {}


_cfg = _load_tool_config()

LABEL_ID = _cfg.get("label_id", _DEFAULTS["label_id"])
EXCLUDED_RELEASE_IDS = frozenset(
    _cfg.get("excluded_release_ids", _DEFAULTS["excluded_release_ids"])
)
IGNORED_ARTIST_IDS = frozenset(
    _cfg.get("ignored_artist_ids", _DEFAULTS["ignored_artist_ids"])
)
SITE_URL = _cfg.get("site_url", _DEFAULTS["site_url"])

PURCHASE_STORE_NAMES = {
    "junodownload": "Juno Download",
    "beatport": "Beatport",
    "traxsource": "Traxsource",
    "bandcamp": "Bandcamp",
}

MB_USER_AGENT = "martinevelabelreleases"
MB_VERSION = "1.0"
