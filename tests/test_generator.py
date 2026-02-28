"""Tests for HTML generator."""

from pathlib import Path

import pytest

from mblabelsite.database import Database
from mblabelsite.generator import (
    generate_artist_page,
    generate_homepage,
    generate_release_page,
)
from mblabelsite.models import Artist, PurchaseLink, Release, Track


@pytest.fixture
def db(tmp_db):
    return Database(tmp_db)


@pytest.fixture
def test_data_dir(tmp_path):
    """Temporary data dir with covers subdirectory."""
    d = tmp_path / "data"
    d.mkdir()
    (d / "covers").mkdir()
    return d


@pytest.fixture
def setup_dirs(tmp_path, template_dir, input_dir):
    """Set up output dir with necessary template and input structure."""
    out = tmp_path / "output"
    for subdir in ["releases", "artists", "images/covers", "images/artists",
                   "images/physical", "images/site", "css"]:
        (out / subdir).mkdir(parents=True, exist_ok=True)

    return out


@pytest.fixture
def sample_release():
    return Release(
        id="test-release-1",
        artist_credit="Test Artist",
        title="Test Title",
        date="2024-01-15",
        label="Test Label",
        catno="TT001",
        slug="test-artist-test-title",
        artist_ids=["art-1"],
        remixer_ids=[],
        mastering_ids=[],
        cover_art_designer_ids=[],
        tracks=[
            Track(position=1, title="Song One", length_ms=300000),
            Track(position=2, title="Song Two", length_ms=185000),
        ],
        purchase_links=[
            PurchaseLink(store_name="Bandcamp", url="https://test.bandcamp.com", position=0),
        ],
        artist_credit_phrase="Test Artist",
    )


class TestGenerateReleasePage:
    def test_generates_html_file(
        self, db, sample_release, test_data_dir, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))

        # Create a dummy cover image in data_dir
        cover_path = test_data_dir / "covers" / sample_release.id
        _create_dummy_image(cover_path)

        result = generate_release_page(
            sample_release, db, template_dir, input_dir, test_data_dir, setup_dirs
        )
        assert result is True

        # Check UUID file exists
        uuid_file = setup_dirs / "releases" / f"{sample_release.id}.html"
        assert uuid_file.exists()

        # Check slug file exists
        slug_file = setup_dirs / "releases" / "test-artist-test-title.html"
        assert slug_file.exists()

        # Check content
        content = uuid_file.read_text()
        assert "Test Artist" in content
        assert "Test Title" in content
        assert "2024" in content
        assert "TT001" in content

    def test_artist_links_in_output(
        self, db, sample_release, test_data_dir, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))

        cover_path = test_data_dir / "covers" / sample_release.id
        _create_dummy_image(cover_path)

        generate_release_page(sample_release, db, template_dir, input_dir, test_data_dir, setup_dirs)

        content = (setup_dirs / "releases" / f"{sample_release.id}.html").read_text()
        assert 'href="../artists/test-artist.html"' in content
        assert ">Test Artist</a>" in content

    def test_track_listing(
        self, db, sample_release, test_data_dir, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))

        cover_path = test_data_dir / "covers" / sample_release.id
        _create_dummy_image(cover_path)

        generate_release_page(sample_release, db, template_dir, input_dir, test_data_dir, setup_dirs)

        content = (setup_dirs / "releases" / f"{sample_release.id}.html").read_text()
        assert "Song One (5:00)" in content
        assert "Song Two (3:05)" in content

    def test_purchase_links(
        self, db, sample_release, test_data_dir, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))

        cover_path = test_data_dir / "covers" / sample_release.id
        _create_dummy_image(cover_path)

        generate_release_page(sample_release, db, template_dir, input_dir, test_data_dir, setup_dirs)

        content = (setup_dirs / "releases" / f"{sample_release.id}.html").read_text()
        assert "Bandcamp" in content
        assert "https://test.bandcamp.com" in content

    def test_bandcamp_embed(
        self, db, sample_release, test_data_dir, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))
        db.set_bandcamp_embed(sample_release.id, "<iframe>bandcamp</iframe>")

        cover_path = test_data_dir / "covers" / sample_release.id
        _create_dummy_image(cover_path)

        generate_release_page(sample_release, db, template_dir, input_dir, test_data_dir, setup_dirs)

        content = (setup_dirs / "releases" / f"{sample_release.id}.html").read_text()
        assert "<iframe>bandcamp</iframe>" in content

    def test_soundcloud_embed(
        self, db, sample_release, test_data_dir, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))
        db.set_soundcloud_embed(sample_release.id, "https://soundcloud.com/test")

        cover_path = test_data_dir / "covers" / sample_release.id
        _create_dummy_image(cover_path)

        generate_release_page(sample_release, db, template_dir, input_dir, test_data_dir, setup_dirs)

        content = (setup_dirs / "releases" / f"{sample_release.id}.html").read_text()
        assert "https://soundcloud.com/test" in content


class TestGenerateArtistPage:
    def test_generates_artist_html(
        self, db, sample_release, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))

        result = generate_artist_page("art-1", db, template_dir, input_dir, setup_dirs)
        assert result is True

        # UUID-named file
        uuid_file = setup_dirs / "artists" / "art-1.html"
        assert uuid_file.exists()

        # Slug-named file
        slug_file = setup_dirs / "artists" / "test-artist.html"
        assert slug_file.exists()

        content = slug_file.read_text()
        assert "Test Artist" in content

    def test_artist_page_has_releases(
        self, db, sample_release, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))

        generate_artist_page("art-1", db, template_dir, input_dir, setup_dirs)

        content = (setup_dirs / "artists" / "test-artist.html").read_text()
        assert "Test Title" in content
        assert "2024" in content

    def test_ignored_release_excluded(
        self, db, sample_release, setup_dirs, template_dir, input_dir
    ):
        db.upsert_release(sample_release)
        db.upsert_artist(Artist(id="art-1", name="Test Artist", slug="test-artist"))
        db.set_ignored_release(sample_release.id)

        generate_artist_page("art-1", db, template_dir, input_dir, setup_dirs)

        content = (setup_dirs / "artists" / "test-artist.html").read_text()
        assert "Test Title" not in content


class TestGenerateHomepage:
    def test_generates_index_html(
        self, db, sample_release, setup_dirs, template_dir
    ):
        db.upsert_release(sample_release)

        result = generate_homepage(db, template_dir, setup_dirs)
        assert result is True

        index = setup_dirs / "index.html"
        assert index.exists()

        content = index.read_text()
        assert "tici taci records" in content
        assert sample_release.id in content

    def test_ignored_release_excluded_from_homepage(
        self, db, sample_release, setup_dirs, template_dir
    ):
        db.upsert_release(sample_release)
        db.set_ignored_release(sample_release.id)

        generate_homepage(db, template_dir, setup_dirs)

        content = (setup_dirs / "index.html").read_text()
        assert sample_release.id not in content


def _create_dummy_image(path: Path):
    """Create a small valid PNG image at the given path."""
    from PIL import Image as PILImage

    img = PILImage.new("RGB", (100, 100), color="red")
    img.save(str(path), format="PNG")
