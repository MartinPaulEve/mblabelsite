"""Tests for fetcher orchestration module."""

from unittest.mock import patch

import pytest

from mblabelsite.database import Database
from mblabelsite.fetcher import (
    FetchError,
    _collect_artist_ids,
    _ensure_artists,
    refresh,
    total_refresh,
    update,
)
from mblabelsite.mb_client import CoverArtError
from mblabelsite.models import Artist, Release


@pytest.fixture
def db(tmp_db):
    return Database(tmp_db)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "covers").mkdir()
    return d


@pytest.fixture
def output_dir(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "releases").mkdir()
    return out


class TestCollectArtistIds:
    def test_collects_from_all_roles(self, db):
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="A",
                title="T",
                date="2024-01-01",
                slug="a-t",
                artist_ids=["a1"],
                remixer_ids=["r1"],
                mastering_ids=["m1"],
                cover_art_designer_ids=["d1"],
            )
        )
        ids = _collect_artist_ids(db)
        assert ids == {"a1", "r1", "m1", "d1"}

    def test_excludes_ignored_artists(self, db):
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="A",
                title="T",
                date="2024-01-01",
                slug="a-t",
                artist_ids=["8a26ca9b-d542-449b-a5e7-224da9eb8a77", "a1"],
            )
        )
        ids = _collect_artist_ids(db)
        assert "8a26ca9b-d542-449b-a5e7-224da9eb8a77" not in ids
        assert "a1" in ids


class TestEnsureArtists:
    def test_fetches_missing_artists(self, db):
        with patch("mblabelsite.fetcher.mb_client") as mock_mb:
            mock_mb.fetch_artist.return_value = Artist(
                id="a1", name="Artist One", slug="artist-one"
            )
            _ensure_artists(db, {"a1"})
            mock_mb.fetch_artist.assert_called_once_with("a1", None)
            assert db.get_artist("a1") is not None

    def test_skips_existing_artists(self, db):
        db.upsert_artist(Artist(id="a1", name="Already Here", slug="already-here"))
        with patch("mblabelsite.fetcher.mb_client") as mock_mb:
            _ensure_artists(db, {"a1"})
            mock_mb.fetch_artist.assert_not_called()


class TestUpdate:
    @patch("mblabelsite.fetcher.mb_client")
    def test_incremental_update(self, mock_mb, db, data_dir, output_dir):
        # Existing release in DB
        db.upsert_release(
            Release(
                id="existing",
                artist_credit="A",
                title="T",
                date="2024-01-01",
                slug="a-t",
            )
        )
        db.set_label_releases(["existing"])

        # API returns existing + new
        mock_mb.get_label_releases.return_value = ["existing", "new-release"]
        mock_mb.fetch_release.return_value = Release(
            id="new-release",
            artist_credit="B",
            title="New",
            date="2024-06-01",
            slug="b-new",
        )
        mock_mb.fetch_cover_art.return_value = b"fake-image-data"
        mock_mb.fetch_artist.return_value = Artist(id="a1", name="A", slug="a")

        update(db, "label-id", data_dir, output_dir)

        assert db.get_release("new-release") is not None
        assert db.get_release("existing") is not None
        # fetch_release should only be called for the new release
        mock_mb.fetch_release.assert_called_once_with("new-release", None)
        # Cover art saved to data_dir
        assert (data_dir / "covers" / "new-release").read_bytes() == b"fake-image-data"

    @patch("mblabelsite.fetcher.mb_client")
    def test_handles_deleted_release(self, mock_mb, db, data_dir, output_dir):
        db.upsert_release(
            Release(
                id="to-delete",
                artist_credit="A",
                title="Gone",
                date="2024-01-01",
                slug="a-gone",
            )
        )
        db.set_label_releases(["to-delete"])

        # API no longer returns the release
        mock_mb.get_label_releases.return_value = []

        update(db, "label-id", data_dir, output_dir)

        assert db.get_release("to-delete") is None


class TestGetReleaseFetchedAt:
    def test_returns_fetched_at_for_existing_release(self, db):
        db.upsert_release(
            Release(
                id="r1",
                artist_credit="A",
                title="T",
                date="2024-01-01",
                slug="a-t",
            )
        )
        result = db.get_release_fetched_at("r1")
        assert result is not None
        assert isinstance(result, str)

    def test_returns_none_for_missing_release(self, db):
        result = db.get_release_fetched_at("nonexistent")
        assert result is None


class TestRefreshResume:
    def _make_release(self, rid):
        return Release(
            id=rid,
            artist_credit="A",
            title=f"Title {rid}",
            date="2024-01-01",
            slug=f"a-{rid}",
        )

    @patch("mblabelsite.fetcher.mb_client")
    def test_refresh_resume_skips_releases_before_resume_after(
        self, mock_mb, db, data_dir
    ):
        mock_mb.get_label_releases.return_value = ["r1", "r2", "r3"]
        mock_mb.fetch_release.side_effect = [
            self._make_release("r3"),
        ]
        mock_mb.fetch_cover_art.return_value = b"img"

        refresh(db, "label-id", data_dir, resume_after="r2")

        # Only r3 should be fetched (r1 and r2 skipped)
        mock_mb.fetch_release.assert_called_once_with("r3", None)

    @patch("mblabelsite.fetcher.mb_client")
    def test_refresh_without_resume_processes_all(self, mock_mb, db, data_dir):
        mock_mb.get_label_releases.return_value = ["r1", "r2"]
        mock_mb.fetch_release.side_effect = [
            self._make_release("r1"),
            self._make_release("r2"),
        ]
        mock_mb.fetch_cover_art.return_value = b"img"

        refresh(db, "label-id", data_dir)

        assert mock_mb.fetch_release.call_count == 2

    @patch("mblabelsite.fetcher.mb_client")
    def test_refresh_error_includes_last_success_id(self, mock_mb, db, data_dir):
        mock_mb.get_label_releases.return_value = ["r1", "r2", "r3"]
        mock_mb.fetch_release.side_effect = [
            self._make_release("r1"),
            self._make_release("r2"),
        ]
        # r1 cover art succeeds, r2 cover art fails
        mock_mb.fetch_cover_art.side_effect = [
            b"img",
            CoverArtError("fail"),
        ]

        with pytest.raises(FetchError, match="--resume r1"):
            refresh(db, "label-id", data_dir)


class TestTotalRefreshResume:
    def _make_release(self, rid):
        return Release(
            id=rid,
            artist_credit="A",
            title=f"Title {rid}",
            date="2024-01-01",
            slug=f"a-{rid}",
        )

    @patch("mblabelsite.fetcher.mb_client")
    def test_total_refresh_resume_skips_cover_deletion(self, mock_mb, db, data_dir):
        # Pre-create a cover art file in data_dir
        cover_file = data_dir / "covers" / "r1"
        cover_file.write_bytes(b"existing-cover")

        mock_mb.get_label_releases.return_value = ["r1", "r2"]
        mock_mb.fetch_release.side_effect = [
            self._make_release("r2"),
        ]
        mock_mb.fetch_cover_art.return_value = b"img"

        total_refresh(db, "label-id", data_dir, resume_after="r1")

        # Cover art for r1 should NOT have been deleted
        assert cover_file.exists()
        assert cover_file.read_bytes() == b"existing-cover"

    @patch("mblabelsite.fetcher.mb_client")
    def test_total_refresh_without_resume_deletes_covers(
        self, mock_mb, db, data_dir
    ):
        # Pre-create a cover art file in data_dir
        cover_file = data_dir / "covers" / "r1"
        cover_file.write_bytes(b"existing-cover")

        mock_mb.get_label_releases.return_value = ["r1"]
        mock_mb.fetch_release.side_effect = [self._make_release("r1")]
        mock_mb.fetch_cover_art.return_value = b"img"

        total_refresh(db, "label-id", data_dir)

        # Original file should have been deleted (rmtree), new one created
        assert cover_file.exists()
        assert cover_file.read_bytes() == b"img"

    @patch("mblabelsite.fetcher.mb_client")
    def test_total_refresh_resume_skips_releases(self, mock_mb, db, data_dir):
        mock_mb.get_label_releases.return_value = ["r1", "r2", "r3"]
        mock_mb.fetch_release.side_effect = [
            self._make_release("r3"),
        ]
        mock_mb.fetch_cover_art.return_value = b"img"

        total_refresh(db, "label-id", data_dir, resume_after="r2")

        mock_mb.fetch_release.assert_called_once_with("r3", None)

    @patch("mblabelsite.fetcher.mb_client")
    def test_total_refresh_error_includes_last_success_id(
        self, mock_mb, db, data_dir
    ):
        mock_mb.get_label_releases.return_value = ["r1", "r2"]
        mock_mb.fetch_release.side_effect = [
            self._make_release("r1"),
            self._make_release("r2"),
        ]
        mock_mb.fetch_cover_art.side_effect = [
            b"img",
            CoverArtError("fail"),
        ]

        with pytest.raises(FetchError, match="--resume r1"):
            total_refresh(db, "label-id", data_dir)
