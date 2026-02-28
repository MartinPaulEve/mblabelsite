"""One-time migration from flat-file cache to SQLite."""

import ast
import logging
from pathlib import Path

from mblabelsite.config import EXCLUDED_RELEASE_IDS
from mblabelsite.database import Database
from mblabelsite.models import Artist, PurchaseLink, Release, Track
from mblabelsite.slug import get_artist_slug, get_release_slug

logger = logging.getLogger(__name__)


def migrate_all(db: Database, data_dir: Path | str, input_dir: Path | str):
    """Migrate all flat-file data into the SQLite database."""
    data_dir = Path(data_dir)
    input_dir = Path(input_dir)

    # 1. Read release IDs from ids.txt
    release_ids = _read_release_ids(data_dir)
    logger.info("Found %d release IDs", len(release_ids))

    # 2. Migrate releases
    for rid in release_ids:
        if rid in EXCLUDED_RELEASE_IDS:
            continue
        _migrate_release(db, rid, data_dir, input_dir)

    # 3. Migrate artists
    _migrate_artists(db, data_dir, input_dir)

    # 4. Migrate user data from input/
    _migrate_user_data(db, input_dir)

    # 5. Set label releases
    db.set_label_releases(
        [rid for rid in release_ids if rid not in EXCLUDED_RELEASE_IDS]
    )

    logger.info("Migration complete")


def _read_release_ids(data_dir: Path) -> list[str]:
    """Read release IDs from data/ids.txt (Python repr format)."""
    ids_file = data_dir / "ids.txt"
    if not ids_file.exists():
        logger.warning("ids.txt not found")
        return []

    content = ids_file.read_text()
    try:
        pages = ast.literal_eval(content)
    except (ValueError, SyntaxError):
        logger.error("Cannot parse ids.txt")
        return []

    release_list = []
    for page in pages:
        for r in page.get("release-list", []):
            release_list.append(r)

    release_list.sort(key=lambda r: r.get("date", ""), reverse=True)
    return [r["id"] for r in release_list]


def _migrate_release(db: Database, release_id: str, data_dir: Path, input_dir: Path):
    """Migrate a single release from flat files."""
    releases_dir = data_dir / "releases"

    # Read main data
    data_file = releases_dir / f"{release_id}.data"
    if not data_file.exists():
        logger.warning("No data file for release %s", release_id)
        return

    lines = data_file.read_text().splitlines()
    if len(lines) < 5:
        logger.warning("Incomplete data file for release %s", release_id)
        return

    artist_credit = lines[0]
    title = lines[1]
    date = lines[2]
    label = lines[3]
    catno = lines[4]

    # Read artist IDs
    artist_ids = _read_id_list(releases_dir / f"{release_id}.artist")
    remixer_ids = _read_id_list(releases_dir / f"{release_id}.remixer")
    mastering_ids = _read_id_list(releases_dir / f"{release_id}.master")

    # Read tracks
    track_titles = _read_lines(releases_dir / f"{release_id}.track_list")
    track_lengths = _read_lines(releases_dir / f"{release_id}.track_length_list")

    tracks = []
    for i, title_text in enumerate(track_titles):
        length_ms = 0
        if i < len(track_lengths):
            try:
                length_ms = int(track_lengths[i])
            except ValueError:
                pass
        tracks.append(Track(position=i + 1, title=title_text, length_ms=length_ms))

    # Read purchase links
    purchase_links = _read_purchases(data_dir / "purchases" / f"{release_id}.purchase")

    # Compute slug - use first credited artist name (matching original behavior)
    first_artist_name = _find_first_artist_name(
        artist_credit, artist_ids, data_dir / "artists"
    )
    slug = get_release_slug(release_id, first_artist_name, title, input_dir)

    # Clean up title (smart quotes)
    title = title.replace("\u201c", "&#8220;")
    title = title.replace("\u201d", "&#8221;")

    release = Release(
        id=release_id,
        artist_credit=artist_credit,
        title=title,
        date=date,
        label=label,
        catno=catno,
        artist_ids=artist_ids,
        remixer_ids=remixer_ids,
        mastering_ids=mastering_ids,
        cover_art_designer_ids=[],
        tracks=tracks,
        purchase_links=purchase_links,
        artist_credit_phrase=artist_credit,
        slug=slug,
    )
    db.upsert_release(release)
    logger.debug("Migrated release: %s - %s", artist_credit, title)


def _migrate_artists(db: Database, data_dir: Path, input_dir: Path):
    """Migrate all artists from data/artists/*.artistinfo."""
    artists_dir = data_dir / "artists"
    if not artists_dir.exists():
        return

    for info_file in artists_dir.glob("*.artistinfo"):
        artist_id = info_file.stem
        name = info_file.read_text().strip()
        if not name:
            continue
        slug = get_artist_slug(artist_id, name, input_dir)
        db.upsert_artist(Artist(id=artist_id, name=name, slug=slug))
        logger.debug("Migrated artist: %s (%s)", name, artist_id)


def _migrate_user_data(db: Database, input_dir: Path):
    """Migrate user-provided data from input/ subdirectories."""
    # Bandcamp embeds - preserve content as-is (original code used file.read())
    bc_dir = input_dir / "bandcamp"
    if bc_dir.exists():
        for f in bc_dir.glob("*.bandcamp"):
            db.set_bandcamp_embed(f.stem, f.read_text())

    # SoundCloud embeds - preserve content as-is (original code used file.read())
    sc_dir = input_dir / "soundcloud"
    if sc_dir.exists():
        for f in sc_dir.glob("*.soundcloud"):
            db.set_soundcloud_embed(f.stem, f.read_text())

    # Release rewrites
    rw_dir = input_dir / "rewrites"
    if rw_dir.exists():
        for f in rw_dir.glob("*.rewrite"):
            db.set_release_rewrite(f.stem, f.read_text().strip())

    # Artist rewrites
    arw_dir = input_dir / "artist_rewrites"
    if arw_dir.exists():
        for f in arw_dir.glob("*.rewrite"):
            db.set_artist_rewrite(f.stem, f.read_text().strip())

    # Notes - preserve content as-is
    notes_dir = input_dir / "notes"
    if notes_dir.exists():
        for f in notes_dir.glob("*.note"):
            db.set_release_note(f.stem, f.read_text())

    # Physical releases - preserve content as-is
    phys_dir = input_dir / "physical"
    if phys_dir.exists():
        for f in phys_dir.glob("*.physical"):
            db.set_physical_release(f.stem, f.read_text())

    # Artist ordering
    ao_dir = input_dir / "artist_ordering"
    if ao_dir.exists():
        for f in ao_dir.glob("*.order"):
            lines = [line.strip() for line in f.read_text().splitlines() if line.strip()]
            if lines:
                db.set_artist_ordering(f.stem, lines)

    # Mastering ordering
    mo_dir = input_dir / "mastering_ordering"
    if mo_dir.exists():
        for f in mo_dir.glob("*.order"):
            lines = [line.strip() for line in f.read_text().splitlines() if line.strip()]
            if lines:
                db.set_mastering_ordering(f.stem, lines)

    # Ignored releases (check for .ignore files)
    ig_dir = input_dir / "ignore"
    if ig_dir.exists():
        for f in ig_dir.glob("*.ignore"):
            db.set_ignored_release(f.stem)


def _find_first_artist_name(
    artist_credit: str, artist_ids: list[str], artists_dir: Path
) -> str:
    """Find the first credited artist name.

    The original code used release['artist-credit'][0]['artist']['name']
    from the API. During migration, we approximate this by checking which
    artist's name the credit phrase starts with.
    """
    if not artist_ids:
        return artist_credit

    # Look up each artist name and check if the credit starts with it
    for aid in artist_ids:
        info_file = artists_dir / f"{aid}.artistinfo"
        if info_file.exists():
            name = info_file.read_text().strip()
            if name and artist_credit.startswith(name):
                return name

    # Fallback: use the full credit phrase
    return artist_credit


def _read_id_list(path: Path) -> list[str]:
    """Read a file of newline-separated IDs, filtering blanks."""
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _read_lines(path: Path) -> list[str]:
    """Read non-empty lines from a file."""
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _read_purchases(path: Path) -> list[PurchaseLink]:
    """Read purchase links from a .purchase file (format: StoreName*URL)."""
    if not path.exists():
        return []
    links = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("*", 1)
        if len(parts) == 2:
            links.append(
                PurchaseLink(
                    store_name=parts[0],
                    url=parts[1],
                    position=len(links),
                )
            )
    return links
