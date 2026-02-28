"""Filename sanitization and slug computation."""

import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in file paths and URL slugs.

    Converts to lowercase, replaces spaces with hyphens,
    removes invalid characters, and cleans up consecutive hyphens.
    """
    name = name.lower()
    name = name.replace(" ", "-")
    name = re.sub(r'[/\\:*?"<>|]', "", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name


def get_release_slug(
    release_id: str,
    artist_name: str,
    title: str,
    input_dir: Path | str | None = None,
) -> str:
    """Compute slug for a release.

    Checks input/rewrites/ for a manual override first,
    then falls back to computed slug from artist + title.
    """
    if input_dir is not None:
        rewrite_path = Path(input_dir) / "rewrites" / f"{release_id}.rewrite"
        if rewrite_path.exists():
            return rewrite_path.read_text().strip()

    return sanitize_filename(artist_name) + "-" + sanitize_filename(title)


def get_artist_slug(
    artist_id: str,
    artist_name: str,
    input_dir: Path | str | None = None,
) -> str:
    """Compute slug for an artist.

    Checks input/artist_rewrites/ for a manual override first,
    then falls back to computed slug from artist name.
    """
    if input_dir is not None:
        rewrite_path = Path(input_dir) / "artist_rewrites" / f"{artist_id}.rewrite"
        if rewrite_path.exists():
            return rewrite_path.read_text().strip()

    return sanitize_filename(artist_name)
