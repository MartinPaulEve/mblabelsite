"""Tests for CLI commands."""


from pathlib import Path

import pytest
from click.testing import CliRunner

from mblabelsite.bandcamp import BandcampError
from mblabelsite.cli import cli
from mblabelsite.database import Database
from mblabelsite.models import Artist, Release


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def db_setup(tmp_path):
    """Set up a temp database with sample data and return paths."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    db = Database(data_dir / "cache.db")
    db.upsert_release(
        Release(
            id="r1",
            artist_credit="Test Artist",
            title="Electric Dreams",
            date="2024-01-15",
            label="Test Label",
            catno="TT001",
            slug="test-artist-electric-dreams",
            artist_ids=["a1"],
        )
    )
    db.upsert_artist(Artist(id="a1", name="Test Artist", slug="test-artist"))
    db.close()

    return {
        "data_dir": str(data_dir),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "template_dir": "templates",
    }


def _base_args(setup):
    return [
        "--data-dir", setup["data_dir"],
        "--input-dir", setup["input_dir"],
        "--output-dir", setup["output_dir"],
    ]


class TestListReleases:
    def test_lists_releases(self, runner, db_setup):
        result = runner.invoke(cli, _base_args(db_setup) + ["list-releases"])
        assert result.exit_code == 0
        assert "Electric Dreams" in result.output
        assert "TT001" in result.output


class TestSearch:
    def test_search_finds_release(self, runner, db_setup):
        result = runner.invoke(cli, _base_args(db_setup) + ["search", "electric"])
        assert result.exit_code == 0
        assert "Electric Dreams" in result.output

    def test_search_no_results(self, runner, db_setup):
        result = runner.invoke(cli, _base_args(db_setup) + ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "No results found" in result.output


class TestShowRelease:
    def test_show_release(self, runner, db_setup):
        result = runner.invoke(
            cli, _base_args(db_setup) + ["show-release", "Electric Dreams"]
        )
        assert result.exit_code == 0
        assert "Electric Dreams" in result.output
        assert "r1" in result.output


class TestDataManipulation:
    def test_add_bandcamp_html(self, runner, db_setup):
        result = runner.invoke(
            cli,
            _base_args(db_setup)
            + ["add-bandcamp-html", "<iframe>test</iframe>", "Electric Dreams"],
        )
        assert result.exit_code == 0
        assert "Bandcamp embed set" in result.output
        db = Database(Path(db_setup["data_dir"]) / "cache.db")
        try:
            assert db.get_bandcamp_embed("r1") == "<iframe>test</iframe>"
        finally:
            db.close()

    def test_add_bandcamp_from_url_stores_generated_embed(
        self, runner, db_setup, monkeypatch
    ):
        monkeypatch.setattr(
            "mblabelsite.cli.embed_from_url",
            lambda url: f"<iframe>{url}</iframe>",
        )
        result = runner.invoke(
            cli,
            _base_args(db_setup)
            + ["add-bandcamp", "https://ticitaci.bandcamp.com/track/netbacks", "Electric Dreams"],
        )
        assert result.exit_code == 0
        assert "Bandcamp embed set" in result.output
        db = Database(Path(db_setup["data_dir"]) / "cache.db")
        try:
            assert db.get_bandcamp_embed("r1") == (
                "<iframe>https://ticitaci.bandcamp.com/track/netbacks</iframe>"
            )
        finally:
            db.close()

    def test_add_bandcamp_reports_lookup_failure(self, runner, db_setup, monkeypatch):
        def _fail(url):
            raise BandcampError("could not find that release on Bandcamp")

        monkeypatch.setattr("mblabelsite.cli.embed_from_url", _fail)
        result = runner.invoke(
            cli,
            _base_args(db_setup)
            + ["add-bandcamp", "https://ticitaci.bandcamp.com/track/nope", "Electric Dreams"],
        )
        assert result.exit_code != 0
        assert "could not find that release on Bandcamp" in result.output
        db = Database(Path(db_setup["data_dir"]) / "cache.db")
        try:
            assert db.get_bandcamp_embed("r1") is None
        finally:
            db.close()

    def test_remove_bandcamp_clears_embed(self, runner, db_setup):
        db = Database(Path(db_setup["data_dir"]) / "cache.db")
        db.set_bandcamp_embed("r1", "<iframe>test</iframe>")
        db.close()
        result = runner.invoke(
            cli, _base_args(db_setup) + ["remove-bandcamp", "Electric Dreams"]
        )
        assert result.exit_code == 0
        assert "Bandcamp embed removed" in result.output
        db = Database(Path(db_setup["data_dir"]) / "cache.db")
        try:
            assert db.get_bandcamp_embed("r1") is None
        finally:
            db.close()

    def test_add_note(self, runner, db_setup):
        result = runner.invoke(
            cli,
            _base_args(db_setup) + ["add-note", "Electric Dreams", "A great release"],
        )
        assert result.exit_code == 0
        assert "Note set" in result.output

    def test_ignore_release(self, runner, db_setup):
        result = runner.invoke(
            cli, _base_args(db_setup) + ["ignore-release", "Electric Dreams"]
        )
        assert result.exit_code == 0
        assert "Ignoring" in result.output


class TestListArtists:
    def test_lists_artists(self, runner, db_setup):
        result = runner.invoke(cli, _base_args(db_setup) + ["list-artists"])
        assert result.exit_code == 0
        assert "Test Artist" in result.output


class TestShowArtist:
    def test_show_artist(self, runner, db_setup):
        result = runner.invoke(
            cli, _base_args(db_setup) + ["show-artist", "Test Artist"]
        )
        assert result.exit_code == 0
        assert "Test Artist" in result.output
        assert "a1" in result.output
