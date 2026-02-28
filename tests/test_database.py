"""Tests for SQLite database layer."""

import pytest

from mblabelsite.database import Database
from mblabelsite.models import Artist, PurchaseLink, Release, Track


@pytest.fixture
def db(tmp_db):
    return Database(tmp_db)


class TestDatabaseInit:
    def test_creates_tables(self, db):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "releases" in table_names
        assert "artists" in table_names
        assert "tracks" in table_names
        assert "purchase_links" in table_names
        assert "release_artists" in table_names
        assert "label_releases" in table_names
        assert "bandcamp_embeds" in table_names
        assert "soundcloud_embeds" in table_names
        assert "release_notes" in table_names
        assert "release_rewrites" in table_names
        assert "artist_rewrites" in table_names
        assert "artist_ordering" in table_names
        assert "mastering_ordering" in table_names
        assert "physical_releases" in table_names
        assert "ignored_releases" in table_names
        assert "schema_version" in table_names


class TestReleaseOperations:
    def test_upsert_and_get_release(self, db):
        release = Release(
            id="rel-1",
            artist_credit="Test Artist",
            title="Test Title",
            date="2024-01-01",
            label="Test Label",
            catno="TT001",
            slug="test-artist-test-title",
            artist_ids=["art-1", "art-2"],
            remixer_ids=["rem-1"],
            mastering_ids=["mas-1"],
            cover_art_designer_ids=[],
            tracks=[
                Track(position=1, title="Song One", length_ms=300000),
                Track(position=2, title="Song Two", length_ms=250000),
            ],
            purchase_links=[
                PurchaseLink(
                    store_name="Bandcamp", url="https://bc.com/test", position=0
                ),
            ],
            artist_credit_phrase="Test Artist",
        )
        db.upsert_release(release)
        got = db.get_release("rel-1")

        assert got is not None
        assert got.id == "rel-1"
        assert got.artist_credit == "Test Artist"
        assert got.title == "Test Title"
        assert got.date == "2024-01-01"
        assert got.label == "Test Label"
        assert got.catno == "TT001"
        assert got.slug == "test-artist-test-title"
        assert got.artist_credit_phrase == "Test Artist"
        assert got.artist_ids == ["art-1", "art-2"]
        assert got.remixer_ids == ["rem-1"]
        assert got.mastering_ids == ["mas-1"]
        assert got.cover_art_designer_ids == []
        assert len(got.tracks) == 2
        assert got.tracks[0].title == "Song One"
        assert got.tracks[1].length_ms == 250000
        assert len(got.purchase_links) == 1
        assert got.purchase_links[0].store_name == "Bandcamp"

    def test_get_nonexistent_release(self, db):
        assert db.get_release("nonexistent") is None

    def test_upsert_updates_existing(self, db):
        release = Release(
            id="rel-1",
            artist_credit="Artist",
            title="Title",
            date="2024-01-01",
            slug="artist-title",
        )
        db.upsert_release(release)

        release.title = "Updated Title"
        release.tracks = [Track(position=1, title="New Track", length_ms=100000)]
        db.upsert_release(release)

        got = db.get_release("rel-1")
        assert got.title == "Updated Title"
        assert len(got.tracks) == 1
        assert got.tracks[0].title == "New Track"

    def test_get_all_releases(self, db):
        for i in range(3):
            db.upsert_release(
                Release(
                    id=f"rel-{i}",
                    artist_credit=f"Artist {i}",
                    title=f"Title {i}",
                    date=f"2024-0{i + 1}-01",
                    slug=f"artist-{i}-title-{i}",
                )
            )
        releases = db.get_all_releases()
        assert len(releases) == 3

    def test_get_all_releases_sorted_by_date_descending(self, db):
        db.upsert_release(
            Release(
                id="old",
                artist_credit="A",
                title="Old",
                date="2020-01-01",
                slug="a-old",
            )
        )
        db.upsert_release(
            Release(
                id="new",
                artist_credit="B",
                title="New",
                date="2024-06-01",
                slug="b-new",
            )
        )
        releases = db.get_all_releases()
        assert releases[0].id == "new"
        assert releases[1].id == "old"

    def test_delete_release(self, db):
        db.upsert_release(
            Release(
                id="rel-del",
                artist_credit="A",
                title="T",
                date="2024-01-01",
                slug="a-t",
                artist_ids=["art-1"],
                tracks=[Track(position=1, title="S", length_ms=1000)],
            )
        )
        db.delete_release("rel-del")
        assert db.get_release("rel-del") is None

    def test_search_releases_by_title(self, db):
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="A",
                title="Electric Dreams",
                date="2024-01-01",
                slug="a-electric-dreams",
            )
        )
        db.upsert_release(
            Release(
                id="r2",
                artist_credit="B",
                title="Night Vision",
                date="2024-02-01",
                slug="b-night-vision",
            )
        )
        results = db.search_releases_by_title("electric")
        assert len(results) == 1
        assert results[0].id == "r1"

    def test_search_case_insensitive(self, db):
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="A",
                title="Electric Dreams",
                date="2024-01-01",
                slug="a-electric-dreams",
            )
        )
        results = db.search_releases_by_title("ELECTRIC")
        assert len(results) == 1


class TestArtistOperations:
    def test_upsert_and_get_artist(self, db):
        artist = Artist(id="art-1", name="Test Artist", slug="test-artist")
        db.upsert_artist(artist)
        got = db.get_artist("art-1")
        assert got is not None
        assert got.id == "art-1"
        assert got.name == "Test Artist"
        assert got.slug == "test-artist"

    def test_get_nonexistent_artist(self, db):
        assert db.get_artist("nonexistent") is None

    def test_get_artists_for_release(self, db):
        db.upsert_artist(Artist(id="a1", name="Alice", slug="alice"))
        db.upsert_artist(Artist(id="a2", name="Bob", slug="bob"))
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="Alice",
                title="T",
                date="2024-01-01",
                slug="alice-t",
                artist_ids=["a1", "a2"],
            )
        )
        artists = db.get_artists_for_release("r1", role="artist")
        assert len(artists) == 2

    def test_get_releases_for_artist(self, db):
        db.upsert_artist(Artist(id="a1", name="Alice", slug="alice"))
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="Alice",
                title="Song A",
                date="2024-01-01",
                slug="alice-song-a",
                artist_ids=["a1"],
            )
        )
        db.upsert_release(
            Release(
                id="r2",
                artist_credit="Alice",
                title="Song B",
                date="2024-06-01",
                slug="alice-song-b",
                artist_ids=["a1"],
            )
        )
        releases = db.get_releases_for_artist("a1", role="artist")
        assert len(releases) == 2
        # Should be sorted by date descending
        assert releases[0].id == "r2"

    def test_get_all_artists(self, db):
        db.upsert_artist(Artist(id="a1", name="Alice", slug="alice"))
        db.upsert_artist(Artist(id="a2", name="Bob", slug="bob"))
        artists = db.get_all_artists()
        assert len(artists) == 2


class TestLabelReleases:
    def test_set_and_get_label_releases(self, db):
        db.set_label_releases(["r1", "r2", "r3"])
        ids = db.get_label_release_ids()
        assert set(ids) == {"r1", "r2", "r3"}

    def test_detect_new_releases(self, db):
        db.set_label_releases(["r1", "r2"])
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="A",
                title="T",
                date="2024-01-01",
                slug="a-t",
            )
        )
        new_ids = db.detect_new_releases(["r1", "r2", "r3"])
        assert set(new_ids) == {"r2", "r3"}

    def test_detect_deleted_releases(self, db):
        db.set_label_releases(["r1", "r2", "r3"])
        deleted = db.detect_deleted_releases(["r1", "r3"])
        assert set(deleted) == {"r2"}


class TestUserData:
    def test_bandcamp_embed(self, db):
        db.set_bandcamp_embed("r1", "<iframe>test</iframe>")
        assert db.get_bandcamp_embed("r1") == "<iframe>test</iframe>"
        db.remove_bandcamp_embed("r1")
        assert db.get_bandcamp_embed("r1") is None

    def test_soundcloud_embed(self, db):
        db.set_soundcloud_embed("r1", "https://soundcloud.com/test")
        assert db.get_soundcloud_embed("r1") == "https://soundcloud.com/test"
        db.remove_soundcloud_embed("r1")
        assert db.get_soundcloud_embed("r1") is None

    def test_release_notes(self, db):
        db.set_release_note("r1", "This is a note.")
        assert db.get_release_note("r1") == "This is a note."
        db.remove_release_note("r1")
        assert db.get_release_note("r1") is None

    def test_release_rewrite(self, db):
        db.set_release_rewrite("r1", "custom-slug")
        assert db.get_release_rewrite("r1") == "custom-slug"
        db.remove_release_rewrite("r1")
        assert db.get_release_rewrite("r1") is None

    def test_artist_rewrite(self, db):
        db.set_artist_rewrite("a1", "custom-artist")
        assert db.get_artist_rewrite("a1") == "custom-artist"
        db.remove_artist_rewrite("a1")
        assert db.get_artist_rewrite("a1") is None

    def test_artist_ordering(self, db):
        db.set_artist_ordering("r1", ["a2", "a1", "a3"])
        assert db.get_artist_ordering("r1") == ["a2", "a1", "a3"]

    def test_mastering_ordering(self, db):
        db.set_mastering_ordering("r1", ["m2", "m1"])
        assert db.get_mastering_ordering("r1") == ["m2", "m1"]

    def test_physical_release(self, db):
        db.set_physical_release("r1", "<p>Buy CD</p>")
        assert db.get_physical_release("r1") == "<p>Buy CD</p>"
        db.remove_physical_release("r1")
        assert db.get_physical_release("r1") is None

    def test_ignored_release(self, db):
        db.set_ignored_release("r1")
        assert db.is_ignored_release("r1") is True
        db.remove_ignored_release("r1")
        assert db.is_ignored_release("r1") is False
