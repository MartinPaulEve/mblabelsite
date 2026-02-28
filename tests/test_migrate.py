"""Tests for flat-file migration."""


import pytest

from mblabelsite.database import Database
from mblabelsite.migrate import (
    _read_id_list,
    _read_purchases,
    migrate_all,
)


@pytest.fixture
def db(tmp_db):
    return Database(tmp_db)


@pytest.fixture
def flat_files(tmp_path):
    """Create a minimal flat-file structure for testing migration."""
    data = tmp_path / "data"
    releases = data / "releases"
    purchases = data / "purchases"
    artists = data / "artists"
    releases.mkdir(parents=True)
    purchases.mkdir(parents=True)
    artists.mkdir(parents=True)

    # ids.txt
    (data / "ids.txt").write_text(
        "[{'release-list': [{'id': 'r1', 'date': '2024-01-01', 'title': 'Test'}]}]"
    )

    # Release data files
    (releases / "r1.data").write_text("Test Artist\nTest Title\n2024-01-01\nTest Label\nTT001")
    (releases / "r1.artist").write_text("a1\n")
    (releases / "r1.remixer").write_text("rem1\n")
    (releases / "r1.master").write_text("mas1\n")
    (releases / "r1.track_list").write_text("Song One\nSong Two\n")
    (releases / "r1.track_length_list").write_text("300000\n250000\n")

    # Purchase file
    (purchases / "r1.purchase").write_text("Bandcamp*https://test.bandcamp.com\n")

    # Artist files
    (artists / "a1.artistinfo").write_text("Test Artist")
    (artists / "a1.artist").write_text("r1\n")
    (artists / "rem1.artistinfo").write_text("DJ Remix")
    (artists / "rem1.remixer").write_text("r1\n")
    (artists / "mas1.artistinfo").write_text("Master Eng")
    (artists / "mas1.master").write_text("r1\n")

    # Input directory
    inp = tmp_path / "input"
    for subdir in ["bandcamp", "soundcloud", "rewrites", "artist_rewrites",
                   "notes", "physical", "artist_ordering", "mastering_ordering", "ignore"]:
        (inp / subdir).mkdir(parents=True)

    (inp / "bandcamp" / "r1.bandcamp").write_text("<iframe>bc</iframe>")
    (inp / "soundcloud" / "r1.soundcloud").write_text("https://sc.com/test")
    (inp / "rewrites" / "r1.rewrite").write_text("custom-slug")
    (inp / "artist_rewrites" / "a1.rewrite").write_text("custom-artist")
    (inp / "notes" / "r1.note").write_text("A test note")

    return {"data": data, "input": inp}


class TestReadIdList:
    def test_reads_ids(self, tmp_path):
        f = tmp_path / "test.ids"
        f.write_text("id1\nid2\n\nid3\n")
        assert _read_id_list(f) == ["id1", "id2", "id3"]

    def test_missing_file(self, tmp_path):
        assert _read_id_list(tmp_path / "missing") == []


class TestReadPurchases:
    def test_reads_purchases(self, tmp_path):
        f = tmp_path / "test.purchase"
        f.write_text("Bandcamp*https://bc.com\nBeatport*https://bp.com\n")
        links = _read_purchases(f)
        assert len(links) == 2
        assert links[0].store_name == "Bandcamp"
        assert links[1].store_name == "Beatport"
        assert links[0].position == 0
        assert links[1].position == 1


class TestMigrateAll:
    def test_migrates_releases(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])

        release = db.get_release("r1")
        assert release is not None
        assert release.artist_credit == "Test Artist"
        assert release.title == "Test Title"
        assert release.date == "2024-01-01"
        assert release.label == "Test Label"
        assert release.catno == "TT001"
        assert release.slug == "custom-slug"  # from rewrite file

    def test_migrates_tracks(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])

        release = db.get_release("r1")
        assert len(release.tracks) == 2
        assert release.tracks[0].title == "Song One"
        assert release.tracks[0].length_ms == 300000

    def test_migrates_purchase_links(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])

        release = db.get_release("r1")
        assert len(release.purchase_links) == 1
        assert release.purchase_links[0].store_name == "Bandcamp"

    def test_migrates_artist_ids(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])

        release = db.get_release("r1")
        assert "a1" in release.artist_ids
        assert "rem1" in release.remixer_ids
        assert "mas1" in release.mastering_ids

    def test_migrates_artists(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])

        artist = db.get_artist("a1")
        assert artist is not None
        assert artist.name == "Test Artist"
        assert artist.slug == "custom-artist"  # from rewrite file

    def test_migrates_bandcamp(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])
        assert db.get_bandcamp_embed("r1") == "<iframe>bc</iframe>"

    def test_migrates_soundcloud(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])
        assert db.get_soundcloud_embed("r1") == "https://sc.com/test"

    def test_migrates_rewrites(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])
        assert db.get_release_rewrite("r1") == "custom-slug"

    def test_migrates_artist_rewrites(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])
        assert db.get_artist_rewrite("a1") == "custom-artist"

    def test_migrates_notes(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])
        assert db.get_release_note("r1") == "A test note"

    def test_sets_label_releases(self, db, flat_files):
        migrate_all(db, flat_files["data"], flat_files["input"])
        ids = db.get_label_release_ids()
        assert "r1" in ids
