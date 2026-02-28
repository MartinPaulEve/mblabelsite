"""MusicBrainz API wrapper with rate limiting."""

import logging
import time

import musicbrainzngs

from mblabelsite.config import (
    EXCLUDED_RELEASE_IDS,
    IGNORED_ARTIST_IDS,
    MB_USER_AGENT,
    MB_VERSION,
    PURCHASE_STORE_NAMES,
)
from mblabelsite.mb_models import (
    MBArtistCredit,
    MBRelease,
)
from mblabelsite.models import Artist, PurchaseLink, Release, Track
from mblabelsite.slug import get_artist_slug, get_release_slug

logger = logging.getLogger(__name__)

# Suppress noisy "uncaught attribute/element" messages from musicbrainzngs
logging.getLogger("musicbrainzngs").setLevel(logging.WARNING)

_last_request_time = 0.0


def _rate_limit():
    """Ensure at least 1 second between API requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_request_time = time.time()


def setup_musicbrainz():
    """Configure the MusicBrainz client user agent."""
    musicbrainzngs.set_useragent(MB_USER_AGENT, MB_VERSION)


def get_label_releases(label_id: str) -> list[str]:
    """Fetch all release IDs for a label, paginated (2 pages of 100).

    Returns a list of release IDs sorted by date descending,
    excluding any IDs in EXCLUDED_RELEASE_IDS.
    """
    _rate_limit()
    page1 = musicbrainzngs.browse_releases(label=label_id, limit=100)
    _rate_limit()
    page2 = musicbrainzngs.browse_releases(label=label_id, limit=100, offset=100)

    release_list = []
    for page in [page1, page2]:
        for r in page.get("release-list", []):
            if r["id"] not in EXCLUDED_RELEASE_IDS:
                release_list.append(r)

    release_list.sort(key=lambda r: r.get("date", ""), reverse=True)
    return [r["id"] for r in release_list]


def fetch_release(release_id: str, input_dir=None) -> Release:
    """Fetch full release details from MusicBrainz and return a Release model."""
    _rate_limit()
    raw = musicbrainzngs.get_release_by_id(
        release_id,
        includes=[
            "artists",
            "recordings",
            "labels",
            "url-rels",
            "artist-rels",
            "recording-level-rels",
            "artist-credits",
        ],
    )["release"]

    mb_release = MBRelease.model_validate(raw)
    return _convert_release(mb_release, input_dir)


def _convert_release(mb: MBRelease, input_dir=None) -> Release:
    """Convert a parsed MBRelease into our internal Release model."""
    # Extract label and catno
    label_name = ""
    catno = ""
    if mb.label_info_list:
        li = mb.label_info_list[0]
        if li.label:
            label_name = li.label.name
        if li.catalog_number:
            catno = li.catalog_number

    # Extract artists from artist-relation-list
    artist_ids = []
    mastering_ids = []
    cover_art_designer_ids = []

    for rel in mb.artist_relation_list:
        aid = rel.artist.id
        if aid in IGNORED_ARTIST_IDS:
            continue
        if rel.type == "mastering":
            if aid not in mastering_ids:
                mastering_ids.append(aid)
        elif rel.type in ("graphic design", "illustration", "design/illustration"):
            if aid not in cover_art_designer_ids:
                cover_art_designer_ids.append(aid)
        else:
            if aid not in artist_ids:
                artist_ids.append(aid)

    # Add artists from artist-credit
    for credit in mb.artist_credit:
        if isinstance(credit, MBArtistCredit):
            aid = credit.artist.id
            if aid not in IGNORED_ARTIST_IDS and aid not in artist_ids:
                artist_ids.append(aid)

    # Extract tracks and remixers from medium-list
    remixer_ids = []
    tracks = []

    for medium in mb.medium_list:
        for track in medium.track_list:
            rec = track.recording
            if mb.artist_credit_phrase == "Various Artists":
                track_title = f"{rec.artist_credit_phrase} - {rec.title}"
            else:
                track_title = rec.title

            length_ms = rec.length if rec.length else 0
            tracks.append(
                Track(
                    position=len(tracks) + 1,
                    title=track_title,
                    length_ms=length_ms,
                )
            )

            for rel in rec.artist_relation_list:
                if rel.type == "remixer":
                    aid = rel.artist.id
                    if aid not in remixer_ids:
                        remixer_ids.append(aid)

    # Extract purchase links
    purchase_links = []
    for url_rel in mb.url_relation_list:
        if url_rel.type == "purchase for download":
            for key, store_name in PURCHASE_STORE_NAMES.items():
                if key in url_rel.target:
                    purchase_links.append(
                        PurchaseLink(
                            store_name=store_name,
                            url=url_rel.target,
                            position=len(purchase_links),
                        )
                    )
                    break

    # Compute slug
    artist_name = ""
    for credit in mb.artist_credit:
        if isinstance(credit, MBArtistCredit):
            artist_name = credit.artist.name
            break

    slug = get_release_slug(mb.id, artist_name, mb.title, input_dir)

    release = Release(
        id=mb.id,
        artist_credit=mb.artist_credit_phrase,
        title=mb.title,
        date=mb.date,
        label=label_name,
        catno=catno,
        artist_ids=artist_ids,
        remixer_ids=remixer_ids,
        mastering_ids=mastering_ids,
        cover_art_designer_ids=cover_art_designer_ids,
        tracks=tracks,
        purchase_links=purchase_links,
        artist_credit_phrase=mb.artist_credit_phrase,
        slug=slug,
    )
    release.cleanup_title()
    return release


def fetch_artist(artist_id: str, input_dir=None) -> Artist:
    """Fetch artist info from MusicBrainz."""
    _rate_limit()
    raw = musicbrainzngs.get_artist_by_id(artist_id)
    name = raw["artist"]["name"]
    slug = get_artist_slug(artist_id, name, input_dir)
    return Artist(id=artist_id, name=name, slug=slug)


class CoverArtError(Exception):
    """Raised when cover art download fails after retries."""


def fetch_cover_art(release_id: str, max_retries: int = 3) -> bytes:
    """Fetch front cover art for a release.

    Retries with exponential backoff on failure.
    Raises CoverArtError if all retries are exhausted.
    """
    for attempt in range(max_retries):
        _rate_limit()
        try:
            return musicbrainzngs.get_image_front(release_id)
        except musicbrainzngs.WebServiceError as exc:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Cover art fetch failed for %s (attempt %d/%d): %s. "
                    "Retrying in %ds...",
                    release_id, attempt + 1, max_retries, exc, wait,
                )
                time.sleep(wait)
            else:
                raise CoverArtError(
                    f"Failed to fetch cover art for {release_id} "
                    f"after {max_retries} attempts: {exc}"
                ) from exc
    raise CoverArtError(f"Failed to fetch cover art for {release_id}")  # unreachable
