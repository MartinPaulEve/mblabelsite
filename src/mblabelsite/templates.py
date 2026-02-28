"""Template loading and rendering."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_template(template_dir: Path | str, template_name: str) -> str | None:
    """Load a template file by name from the template directory."""
    path = Path(template_dir) / template_name
    try:
        return path.read_text()
    except OSError:
        logger.error("Cannot open template file: %s", path)
        return None


def load_release_template(template_dir: Path | str, release_id: str) -> str | None:
    """Load a release template, checking for per-release override first."""
    override = Path(template_dir) / "releases" / f"{release_id}.template"
    if override.exists():
        return override.read_text()
    return load_template(template_dir, "template_release")
