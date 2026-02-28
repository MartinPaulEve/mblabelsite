"""SQLite database layer for caching MusicBrainz data."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from mblabelsite.models import Artist, PurchaseLink, Release, Track

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS releases (
    id TEXT PRIMARY KEY,
    artist_credit TEXT NOT NULL,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    catno TEXT NOT NULL DEFAULT '',
    artist_credit_phrase TEXT NOT NULL DEFAULT '',
    slug TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS release_artists (
    release_id TEXT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    artist_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('artist','remixer','mastering','cover_art')),
    UNIQUE(release_id, artist_id, role)
);

CREATE TABLE IF NOT EXISTS tracks (
    release_id TEXT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    length_ms INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (release_id, position)
);

CREATE TABLE IF NOT EXISTS purchase_links (
    release_id TEXT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    store_name TEXT NOT NULL,
    url TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (release_id, position)
);

CREATE TABLE IF NOT EXISTS artists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS label_releases (
    release_id TEXT PRIMARY KEY,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bandcamp_embeds (
    release_id TEXT PRIMARY KEY,
    embed_code TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS soundcloud_embeds (
    release_id TEXT PRIMARY KEY,
    embed_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS release_notes (
    release_id TEXT PRIMARY KEY,
    note_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS release_rewrites (
    release_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artist_rewrites (
    artist_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artist_ordering (
    release_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (release_id, position)
);

CREATE TABLE IF NOT EXISTS mastering_ordering (
    release_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (release_id, position)
);

CREATE TABLE IF NOT EXISTS physical_releases (
    release_id TEXT PRIMARY KEY,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ignored_releases (
    release_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        existing = self.conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if existing is None:
            self.conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
            self.conn.commit()

    def close(self):
        self.conn.close()

    # --- Release CRUD ---

    def upsert_release(self, release: Release):
        now = _now()
        self.conn.execute(
            """INSERT INTO releases (id, artist_credit, title, date, label, catno,
               artist_credit_phrase, slug, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               artist_credit=excluded.artist_credit, title=excluded.title,
               date=excluded.date, label=excluded.label, catno=excluded.catno,
               artist_credit_phrase=excluded.artist_credit_phrase,
               slug=excluded.slug, fetched_at=excluded.fetched_at""",
            (
                release.id,
                release.artist_credit,
                release.title,
                release.date,
                release.label,
                release.catno,
                release.artist_credit_phrase,
                release.slug,
                now,
            ),
        )

        # Clear and re-insert related data
        self.conn.execute(
            "DELETE FROM release_artists WHERE release_id=?", (release.id,)
        )
        self.conn.execute("DELETE FROM tracks WHERE release_id=?", (release.id,))
        self.conn.execute(
            "DELETE FROM purchase_links WHERE release_id=?", (release.id,)
        )

        for role, ids in [
            ("artist", release.artist_ids),
            ("remixer", release.remixer_ids),
            ("mastering", release.mastering_ids),
            ("cover_art", release.cover_art_designer_ids),
        ]:
            for artist_id in ids:
                self.conn.execute(
                    """INSERT OR IGNORE INTO release_artists
                       (release_id, artist_id, role) VALUES (?, ?, ?)""",
                    (release.id, artist_id, role),
                )

        for track in release.tracks:
            self.conn.execute(
                """INSERT INTO tracks (release_id, position, title, length_ms)
                   VALUES (?, ?, ?, ?)""",
                (release.id, track.position, track.title, track.length_ms),
            )

        for link in release.purchase_links:
            self.conn.execute(
                """INSERT INTO purchase_links (release_id, store_name, url, position)
                   VALUES (?, ?, ?, ?)""",
                (release.id, link.store_name, link.url, link.position),
            )

        self.conn.commit()

    def get_release(self, release_id: str) -> Release | None:
        row = self.conn.execute(
            """SELECT id, artist_credit, title, date, label, catno,
               artist_credit_phrase, slug FROM releases WHERE id=?""",
            (release_id,),
        ).fetchone()
        if row is None:
            return None

        release = Release(
            id=row[0],
            artist_credit=row[1],
            title=row[2],
            date=row[3],
            label=row[4],
            catno=row[5],
            artist_credit_phrase=row[6],
            slug=row[7],
        )

        # Load artists by role
        for role, attr in [
            ("artist", "artist_ids"),
            ("remixer", "remixer_ids"),
            ("mastering", "mastering_ids"),
            ("cover_art", "cover_art_designer_ids"),
        ]:
            rows = self.conn.execute(
                "SELECT artist_id FROM release_artists WHERE release_id=? AND role=?",
                (release_id, role),
            ).fetchall()
            setattr(release, attr, [r[0] for r in rows])

        # Load tracks
        track_rows = self.conn.execute(
            "SELECT position, title, length_ms FROM tracks WHERE release_id=? ORDER BY position",
            (release_id,),
        ).fetchall()
        release.tracks = [
            Track(position=r[0], title=r[1], length_ms=r[2]) for r in track_rows
        ]

        # Load purchase links
        link_rows = self.conn.execute(
            "SELECT store_name, url, position FROM purchase_links WHERE release_id=? ORDER BY position",
            (release_id,),
        ).fetchall()
        release.purchase_links = [
            PurchaseLink(store_name=r[0], url=r[1], position=r[2]) for r in link_rows
        ]

        return release

    def get_all_releases(self) -> list[Release]:
        rows = self.conn.execute(
            "SELECT id FROM releases ORDER BY date DESC"
        ).fetchall()
        releases = []
        for row in rows:
            r = self.get_release(row[0])
            if r:
                releases.append(r)
        return releases

    def delete_release(self, release_id: str):
        self.conn.execute("DELETE FROM releases WHERE id=?", (release_id,))
        self.conn.commit()

    def search_releases_by_title(self, query: str) -> list[Release]:
        rows = self.conn.execute(
            "SELECT id FROM releases WHERE LOWER(title) LIKE LOWER(?) ORDER BY date DESC",
            (f"%{query}%",),
        ).fetchall()
        return [self.get_release(r[0]) for r in rows if self.get_release(r[0])]

    # --- Artist CRUD ---

    def upsert_artist(self, artist: Artist):
        now = _now()
        self.conn.execute(
            """INSERT INTO artists (id, name, slug, fetched_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               name=excluded.name, slug=excluded.slug, fetched_at=excluded.fetched_at""",
            (artist.id, artist.name, artist.slug, now),
        )
        self.conn.commit()

    def get_artist(self, artist_id: str) -> Artist | None:
        row = self.conn.execute(
            "SELECT id, name, slug FROM artists WHERE id=?", (artist_id,)
        ).fetchone()
        if row is None:
            return None
        return Artist(id=row[0], name=row[1], slug=row[2])

    def get_all_artists(self) -> list[Artist]:
        rows = self.conn.execute(
            "SELECT id, name, slug FROM artists ORDER BY name"
        ).fetchall()
        return [Artist(id=r[0], name=r[1], slug=r[2]) for r in rows]

    def get_artists_for_release(self, release_id: str, role: str) -> list[Artist]:
        rows = self.conn.execute(
            """SELECT a.id, a.name, a.slug FROM artists a
               JOIN release_artists ra ON a.id = ra.artist_id
               WHERE ra.release_id=? AND ra.role=?""",
            (release_id, role),
        ).fetchall()
        return [Artist(id=r[0], name=r[1], slug=r[2]) for r in rows]

    def get_releases_for_artist(self, artist_id: str, role: str) -> list[Release]:
        rows = self.conn.execute(
            """SELECT r.id FROM releases r
               JOIN release_artists ra ON r.id = ra.release_id
               WHERE ra.artist_id=? AND ra.role=?
               ORDER BY r.date DESC""",
            (artist_id, role),
        ).fetchall()
        return [self.get_release(r[0]) for r in rows if self.get_release(r[0])]

    # --- Label Releases ---

    def set_label_releases(self, release_ids: list[str]):
        now = _now()
        self.conn.execute("DELETE FROM label_releases")
        for rid in release_ids:
            self.conn.execute(
                "INSERT INTO label_releases (release_id, last_seen) VALUES (?, ?)",
                (rid, now),
            )
        self.conn.commit()

    def get_label_release_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT release_id FROM label_releases"
        ).fetchall()
        return [r[0] for r in rows]

    def get_release_fetched_at(self, release_id: str) -> str | None:
        """Return the fetched_at timestamp for a release, or None if not found."""
        row = self.conn.execute(
            "SELECT fetched_at FROM releases WHERE id=?", (release_id,)
        ).fetchone()
        return row[0] if row else None

    def detect_new_releases(self, current_ids: list[str]) -> list[str]:
        """Return IDs in current_ids that don't have release data in the DB."""
        existing = self.conn.execute("SELECT id FROM releases").fetchall()
        existing_ids = {r[0] for r in existing}
        return [rid for rid in current_ids if rid not in existing_ids]

    def detect_deleted_releases(self, current_ids: list[str]) -> list[str]:
        """Return IDs in label_releases that are not in current_ids."""
        current_set = set(current_ids)
        stored = self.get_label_release_ids()
        return [rid for rid in stored if rid not in current_set]

    # --- User Data Tables ---

    def set_bandcamp_embed(self, release_id: str, embed_code: str):
        self.conn.execute(
            """INSERT INTO bandcamp_embeds (release_id, embed_code) VALUES (?, ?)
               ON CONFLICT(release_id) DO UPDATE SET embed_code=excluded.embed_code""",
            (release_id, embed_code),
        )
        self.conn.commit()

    def get_bandcamp_embed(self, release_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT embed_code FROM bandcamp_embeds WHERE release_id=?", (release_id,)
        ).fetchone()
        return row[0] if row else None

    def remove_bandcamp_embed(self, release_id: str):
        self.conn.execute(
            "DELETE FROM bandcamp_embeds WHERE release_id=?", (release_id,)
        )
        self.conn.commit()

    def set_soundcloud_embed(self, release_id: str, embed_url: str):
        self.conn.execute(
            """INSERT INTO soundcloud_embeds (release_id, embed_url) VALUES (?, ?)
               ON CONFLICT(release_id) DO UPDATE SET embed_url=excluded.embed_url""",
            (release_id, embed_url),
        )
        self.conn.commit()

    def get_soundcloud_embed(self, release_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT embed_url FROM soundcloud_embeds WHERE release_id=?", (release_id,)
        ).fetchone()
        return row[0] if row else None

    def remove_soundcloud_embed(self, release_id: str):
        self.conn.execute(
            "DELETE FROM soundcloud_embeds WHERE release_id=?", (release_id,)
        )
        self.conn.commit()

    def set_release_note(self, release_id: str, note_text: str):
        self.conn.execute(
            """INSERT INTO release_notes (release_id, note_text) VALUES (?, ?)
               ON CONFLICT(release_id) DO UPDATE SET note_text=excluded.note_text""",
            (release_id, note_text),
        )
        self.conn.commit()

    def get_release_note(self, release_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT note_text FROM release_notes WHERE release_id=?", (release_id,)
        ).fetchone()
        return row[0] if row else None

    def remove_release_note(self, release_id: str):
        self.conn.execute(
            "DELETE FROM release_notes WHERE release_id=?", (release_id,)
        )
        self.conn.commit()

    def set_release_rewrite(self, release_id: str, slug: str):
        self.conn.execute(
            """INSERT INTO release_rewrites (release_id, slug) VALUES (?, ?)
               ON CONFLICT(release_id) DO UPDATE SET slug=excluded.slug""",
            (release_id, slug),
        )
        self.conn.commit()

    def get_release_rewrite(self, release_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT slug FROM release_rewrites WHERE release_id=?", (release_id,)
        ).fetchone()
        return row[0] if row else None

    def remove_release_rewrite(self, release_id: str):
        self.conn.execute(
            "DELETE FROM release_rewrites WHERE release_id=?", (release_id,)
        )
        self.conn.commit()

    def set_artist_rewrite(self, artist_id: str, slug: str):
        self.conn.execute(
            """INSERT INTO artist_rewrites (artist_id, slug) VALUES (?, ?)
               ON CONFLICT(artist_id) DO UPDATE SET slug=excluded.slug""",
            (artist_id, slug),
        )
        self.conn.commit()

    def get_artist_rewrite(self, artist_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT slug FROM artist_rewrites WHERE artist_id=?", (artist_id,)
        ).fetchone()
        return row[0] if row else None

    def remove_artist_rewrite(self, artist_id: str):
        self.conn.execute(
            "DELETE FROM artist_rewrites WHERE artist_id=?", (artist_id,)
        )
        self.conn.commit()

    def set_artist_ordering(self, release_id: str, artist_ids: list[str]):
        self.conn.execute(
            "DELETE FROM artist_ordering WHERE release_id=?", (release_id,)
        )
        for pos, aid in enumerate(artist_ids):
            self.conn.execute(
                "INSERT INTO artist_ordering (release_id, artist_id, position) VALUES (?, ?, ?)",
                (release_id, aid, pos),
            )
        self.conn.commit()

    def get_artist_ordering(self, release_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT artist_id FROM artist_ordering WHERE release_id=? ORDER BY position",
            (release_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def set_mastering_ordering(self, release_id: str, artist_ids: list[str]):
        self.conn.execute(
            "DELETE FROM mastering_ordering WHERE release_id=?", (release_id,)
        )
        for pos, aid in enumerate(artist_ids):
            self.conn.execute(
                "INSERT INTO mastering_ordering (release_id, artist_id, position) VALUES (?, ?, ?)",
                (release_id, aid, pos),
            )
        self.conn.commit()

    def get_mastering_ordering(self, release_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT artist_id FROM mastering_ordering WHERE release_id=? ORDER BY position",
            (release_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def set_physical_release(self, release_id: str, content: str):
        self.conn.execute(
            """INSERT INTO physical_releases (release_id, content) VALUES (?, ?)
               ON CONFLICT(release_id) DO UPDATE SET content=excluded.content""",
            (release_id, content),
        )
        self.conn.commit()

    def get_physical_release(self, release_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT content FROM physical_releases WHERE release_id=?", (release_id,)
        ).fetchone()
        return row[0] if row else None

    def remove_physical_release(self, release_id: str):
        self.conn.execute(
            "DELETE FROM physical_releases WHERE release_id=?", (release_id,)
        )
        self.conn.commit()

    def set_ignored_release(self, release_id: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO ignored_releases (release_id) VALUES (?)",
            (release_id,),
        )
        self.conn.commit()

    def is_ignored_release(self, release_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM ignored_releases WHERE release_id=?", (release_id,)
        ).fetchone()
        return row is not None

    def remove_ignored_release(self, release_id: str):
        self.conn.execute(
            "DELETE FROM ignored_releases WHERE release_id=?", (release_id,)
        )
        self.conn.commit()
