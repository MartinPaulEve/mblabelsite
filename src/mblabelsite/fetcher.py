"""Orchestration: fetch releases, artists, covers from MusicBrainz."""

import logging
import shutil
from pathlib import Path

from mblabelsite import mb_client
from mblabelsite.config import IGNORED_ARTIST_IDS
from mblabelsite.database import Database
from mblabelsite.mb_client import CoverArtError

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Raised when a fetch operation fails fatally."""


def _collect_artist_ids(db: Database) -> set[str]:
    """Collect all unique artist IDs from all releases in the database."""
    artist_ids = set()
    for release in db.get_all_releases():
        artist_ids.update(release.artist_ids)
        artist_ids.update(release.remixer_ids)
        artist_ids.update(release.mastering_ids)
        artist_ids.update(release.cover_art_designer_ids)
    return artist_ids - IGNORED_ARTIST_IDS


def _ensure_artists(db: Database, artist_ids: set[str], input_dir: Path | None = None):
    """Fetch and store artist info for any artist IDs not yet in the database."""
    for aid in artist_ids:
        if db.get_artist(aid) is None:
            logger.info("Fetching artist info: %s", aid)
            try:
                artist = mb_client.fetch_artist(aid, input_dir)
                db.upsert_artist(artist)
            except Exception:
                logger.error("Failed to fetch artist %s", aid, exc_info=True)


def _save_cover_art(release_id: str, data_dir: Path, force: bool = False):
    """Download and save cover art to data_dir/covers/ if not already present.

    Raises CoverArtError if download fails after retries.
    """
    covers_dir = data_dir / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    cover_path = covers_dir / release_id

    if cover_path.exists() and not force:
        logger.debug("Cover art already exists: %s", release_id)
        return

    logger.info("Downloading cover art: %s", release_id)
    data = mb_client.fetch_cover_art(release_id)
    cover_path.write_bytes(data)


def update(
    db: Database,
    label_id: str,
    data_dir: Path,
    output_dir: Path,
    input_dir: Path | None = None,
):
    """Incremental update: fetch only new releases, skip existing ones."""
    mb_client.setup_musicbrainz()

    logger.info("Fetching label release list...")
    current_ids = mb_client.get_label_releases(label_id)

    # Detect new and deleted releases
    new_ids = db.detect_new_releases(current_ids)
    deleted_ids = db.detect_deleted_releases(current_ids)

    # Handle deletions
    for rid in deleted_ids:
        logger.info("Removing deleted release: %s", rid)
        db.delete_release(rid)
        # Remove HTML files
        for html_file in (output_dir / "releases").glob(f"{rid}.html"):
            html_file.unlink(missing_ok=True)

    # Fetch new releases
    for rid in new_ids:
        logger.info("Fetching new release: %s", rid)
        try:
            release = mb_client.fetch_release(rid, input_dir)
            db.upsert_release(release)
            _save_cover_art(rid, data_dir)
        except CoverArtError as exc:
            raise FetchError(
                f"Cover art download failed for release {rid}.\n"
                "Run 'mblabelsite refresh' to resume (skips existing covers)."
            ) from exc
        except Exception:
            logger.error("Failed to fetch release %s", rid, exc_info=True)

    # Update label releases tracking
    db.set_label_releases(current_ids)

    # Ensure all artists are fetched
    _ensure_artists(db, _collect_artist_ids(db), input_dir)


def refresh(
    db: Database,
    label_id: str,
    data_dir: Path,
    input_dir: Path | None = None,
    resume_after: str | None = None,
):
    """Re-fetch metadata for ALL releases, keep existing cover art."""
    mb_client.setup_musicbrainz()

    logger.info("Fetching label release list...")
    current_ids = mb_client.get_label_releases(label_id)

    skipping = resume_after is not None
    last_success_id = None

    for rid in current_ids:
        if skipping:
            if rid == resume_after:
                skipping = False
            logger.info("Skipping already-processed release: %s", rid)
            continue

        logger.info("Refreshing release: %s", rid)
        try:
            release = mb_client.fetch_release(rid, input_dir)
            db.upsert_release(release)
            _save_cover_art(rid, data_dir, force=False)
            last_success_id = rid
        except CoverArtError as exc:
            resume_hint = f" --resume {last_success_id}" if last_success_id else ""
            raise FetchError(
                f"Cover art download failed for release {rid}.\n"
                f"Run 'mblabelsite refresh{resume_hint}' to resume."
            ) from exc
        except Exception:
            logger.error("Failed to fetch release %s", rid, exc_info=True)

    db.set_label_releases(current_ids)
    _ensure_artists(db, _collect_artist_ids(db), input_dir)


def total_refresh(
    db: Database,
    label_id: str,
    data_dir: Path,
    input_dir: Path | None = None,
    resume_after: str | None = None,
):
    """Re-fetch everything including cover art."""
    # Only delete cover art on a fresh run, not when resuming
    if resume_after is None:
        covers_dir = data_dir / "covers"
        if covers_dir.exists():
            shutil.rmtree(covers_dir)

    mb_client.setup_musicbrainz()

    logger.info("Fetching label release list...")
    current_ids = mb_client.get_label_releases(label_id)

    skipping = resume_after is not None
    last_success_id = None

    for rid in current_ids:
        if skipping:
            if rid == resume_after:
                skipping = False
            logger.info("Skipping already-processed release: %s", rid)
            continue

        logger.info("Total refreshing release: %s", rid)
        try:
            release = mb_client.fetch_release(rid, input_dir)
            db.upsert_release(release)
            _save_cover_art(rid, data_dir, force=True)
            last_success_id = rid
        except CoverArtError as exc:
            resume_hint = f" --resume {last_success_id}" if last_success_id else ""
            raise FetchError(
                f"Cover art download failed for release {rid}.\n"
                f"Run 'mblabelsite total-refresh{resume_hint}' to resume."
            ) from exc
        except Exception:
            logger.error("Failed to fetch release %s", rid, exc_info=True)

    db.set_label_releases(current_ids)
    _ensure_artists(db, _collect_artist_ids(db), input_dir)
