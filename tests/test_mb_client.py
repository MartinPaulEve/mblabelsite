"""Tests for MusicBrainz API client wrapper."""

from unittest.mock import patch

import pytest

from mblabelsite.mb_client import _convert_release, fetch_artist, fetch_release
from mblabelsite.mb_models import MBRelease


@pytest.fixture
def sample_release_raw():
    """A realistic MusicBrainz release API response."""
    return {
        "id": "0075f435-403a-4494-adc3-08ff6795d751",
        "title": "May Your Toes Kiss The Sand Again",
        "date": "2021-05-07",
        "artist-credit-phrase": "Duncan Gray",
        "artist-credit": [
            {"artist": {"id": "8e262a85-2f47-4b31-bf9a-aef4b9e7415e", "name": "Duncan Gray"}}
        ],
        "artist-relation-list": [
            {
                "type": "producer",
                "artist": {"id": "8e262a85-2f47-4b31-bf9a-aef4b9e7415e", "name": "Duncan Gray"},
            },
            {
                "type": "mastering",
                "artist": {"id": "mas-123", "name": "Master Engineer"},
            },
            {
                "type": "graphic design",
                "artist": {"id": "design-123", "name": "Cover Designer"},
            },
        ],
        "url-relation-list": [
            {
                "type": "purchase for download",
                "target": "https://ticitaci.bandcamp.com/track/may-your-toes-kiss-the-sand-again",
            }
        ],
        "medium-list": [
            {
                "track-list": [
                    {
                        "recording": {
                            "title": "May Your Toes Kiss The Sand Again",
                            "length": "438546",
                            "artist-credit-phrase": "Duncan Gray",
                            "artist-relation-list": [],
                        }
                    }
                ]
            }
        ],
        "label-info-list": [
            {
                "catalog-number": "TTBC 021",
                "label": {"id": "label-id", "name": "tici taci"},
            }
        ],
    }


@pytest.fixture
def va_release_raw():
    """A Various Artists release."""
    return {
        "id": "va-release-1",
        "title": "VA Compilation",
        "date": "2023-01-01",
        "artist-credit-phrase": "Various Artists",
        "artist-credit": [
            {"artist": {"id": "89ad4ac3-39f7-470e-963a-56509c546377", "name": "Various Artists"}}
        ],
        "artist-relation-list": [],
        "url-relation-list": [],
        "medium-list": [
            {
                "track-list": [
                    {
                        "recording": {
                            "title": "Track A",
                            "length": "300000",
                            "artist-credit-phrase": "Artist A",
                        }
                    },
                    {
                        "recording": {
                            "title": "Track B",
                            "length": "250000",
                            "artist-credit-phrase": "Artist B",
                        }
                    },
                ]
            }
        ],
        "label-info-list": [],
    }


class TestConvertRelease:
    def test_basic_conversion(self, sample_release_raw):
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert release.id == "0075f435-403a-4494-adc3-08ff6795d751"
        assert release.title == "May Your Toes Kiss The Sand Again"
        assert release.date == "2021-05-07"
        assert release.artist_credit == "Duncan Gray"
        assert release.label == "tici taci"
        assert release.catno == "TTBC 021"

    def test_artist_extraction(self, sample_release_raw):
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert "8e262a85-2f47-4b31-bf9a-aef4b9e7415e" in release.artist_ids

    def test_mastering_extraction(self, sample_release_raw):
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert "mas-123" in release.mastering_ids
        assert "mas-123" not in release.artist_ids

    def test_cover_art_designer_extraction(self, sample_release_raw):
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert "design-123" in release.cover_art_designer_ids

    def test_purchase_links(self, sample_release_raw):
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert len(release.purchase_links) == 1
        assert release.purchase_links[0].store_name == "Bandcamp"

    def test_track_extraction(self, sample_release_raw):
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert len(release.tracks) == 1
        assert release.tracks[0].title == "May Your Toes Kiss The Sand Again"
        assert release.tracks[0].length_ms == 438546

    def test_slug_computed(self, sample_release_raw):
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert release.slug == "duncan-gray-may-your-toes-kiss-the-sand-again"

    def test_ignored_artist_excluded(self, sample_release_raw):
        """Artists in IGNORED_ARTIST_IDS should not appear in artist_ids."""
        sample_release_raw["artist-credit"].append(
            {"artist": {"id": "89ad4ac3-39f7-470e-963a-56509c546377", "name": "Various Artists"}}
        )
        mb = MBRelease.model_validate(sample_release_raw)
        release = _convert_release(mb)

        assert "89ad4ac3-39f7-470e-963a-56509c546377" not in release.artist_ids

    def test_va_track_titles(self, va_release_raw):
        mb = MBRelease.model_validate(va_release_raw)
        release = _convert_release(mb)

        assert release.tracks[0].title == "Artist A - Track A"
        assert release.tracks[1].title == "Artist B - Track B"

    def test_remixer_extraction(self):
        raw = {
            "id": "test-remix",
            "title": "Remix EP",
            "date": "2024-01-01",
            "artist-credit-phrase": "Test Artist",
            "artist-credit": [
                {"artist": {"id": "art-1", "name": "Test Artist"}}
            ],
            "artist-relation-list": [],
            "url-relation-list": [],
            "medium-list": [
                {
                    "track-list": [
                        {
                            "recording": {
                                "title": "Song (Remix)",
                                "length": "300000",
                                "artist-credit-phrase": "Test Artist",
                                "artist-relation-list": [
                                    {
                                        "type": "remixer",
                                        "artist": {"id": "rem-1", "name": "DJ Remix"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
            "label-info-list": [],
        }
        mb = MBRelease.model_validate(raw)
        release = _convert_release(mb)
        assert "rem-1" in release.remixer_ids

    def test_no_label_info(self, va_release_raw):
        mb = MBRelease.model_validate(va_release_raw)
        release = _convert_release(mb)
        assert release.label == ""
        assert release.catno == ""


class TestFetchRelease:
    @patch("mblabelsite.mb_client.musicbrainzngs")
    @patch("mblabelsite.mb_client._rate_limit")
    def test_fetch_release_calls_api(self, mock_rate, mock_mb, sample_release_raw):
        mock_mb.get_release_by_id.return_value = {"release": sample_release_raw}
        release = fetch_release("0075f435-403a-4494-adc3-08ff6795d751")
        assert release.id == "0075f435-403a-4494-adc3-08ff6795d751"
        mock_mb.get_release_by_id.assert_called_once()


class TestFetchArtist:
    @patch("mblabelsite.mb_client.musicbrainzngs")
    @patch("mblabelsite.mb_client._rate_limit")
    def test_fetch_artist_calls_api(self, mock_rate, mock_mb):
        mock_mb.get_artist_by_id.return_value = {
            "artist": {"id": "art-1", "name": "Test Artist"}
        }
        artist = fetch_artist("art-1")
        assert artist.id == "art-1"
        assert artist.name == "Test Artist"
        assert artist.slug == "test-artist"
