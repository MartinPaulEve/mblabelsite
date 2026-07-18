"""Tests for building Bandcamp embeds from URLs."""

import pytest

from mblabelsite.bandcamp import (
    BandcampError,
    build_embed,
    embed_from_url,
    lookup_item,
    parse_bandcamp_url,
)

TRACK_URL = "https://ticitaci.bandcamp.com/track/netbacks"
ALBUM_URL = "https://ticitaci.bandcamp.com/album/vanishing-point"

TRACK_RESULT = {
    "type": "t",
    "id": 1695430975,
    "name": "Netbacks",
    "band_name": "Duncan Gray",
    "item_url_path": TRACK_URL,
}
ALBUM_RESULT = {
    "type": "a",
    "id": 42,
    "name": "Vanishing Point",
    "band_name": "Duncan Gray",
    "item_url_path": ALBUM_URL,
}


def fake_search(results):
    """Return a search callable yielding the given results for any query."""

    def _search(text, item_type):
        return results

    return _search


class TestParseBandcampUrl:
    def test_parses_track_url(self):
        assert parse_bandcamp_url(TRACK_URL) == ("t", "netbacks")

    def test_parses_album_url(self):
        assert parse_bandcamp_url(ALBUM_URL) == ("a", "vanishing-point")

    def test_ignores_trailing_slash_and_query(self):
        assert parse_bandcamp_url(TRACK_URL + "/?from=embed") == ("t", "netbacks")

    def test_rejects_non_bandcamp_host(self):
        with pytest.raises(BandcampError):
            parse_bandcamp_url("https://example.com/track/netbacks")

    def test_rejects_non_track_or_album_path(self):
        with pytest.raises(BandcampError):
            parse_bandcamp_url("https://ticitaci.bandcamp.com/music")

    def test_rejects_garbage(self):
        with pytest.raises(BandcampError):
            parse_bandcamp_url("not a url")


class TestBuildEmbed:
    def test_track_embed_matches_expected_html(self):
        assert build_embed("t", 1695430975, TRACK_URL, "Netbacks", "Duncan Gray") == (
            '<iframe style="border: 0; width: 100%; height: 120px;" '
            'src="https://bandcamp.com/EmbeddedPlayer/track=1695430975/size=large/'
            "bgcol=ffffff/linkcol=0687f5/tracklist=false/artwork=small/transparent=true/"
            '" seamless><a href="https://ticitaci.bandcamp.com/track/netbacks">'
            "Netbacks by Duncan Gray</a></iframe>"
        )

    def test_album_embed_is_taller_with_tracklist(self):
        html = build_embed("a", 42, ALBUM_URL, "Vanishing Point", "Duncan Gray")
        assert "height: 470px;" in html
        assert "album=42/" in html
        assert "tracklist=true" in html
        assert ">Vanishing Point by Duncan Gray</a>" in html

    def test_escapes_html_in_title_and_artist(self):
        html = build_embed("t", 1, TRACK_URL, "Rock & <Roll>", "A & B")
        assert "<Roll>" not in html
        assert "Rock &amp; &lt;Roll&gt; by A &amp; B" in html


class TestLookupItem:
    def test_returns_metadata_for_matching_result(self):
        assert lookup_item(TRACK_URL, search=fake_search([TRACK_RESULT])) == {
            "item_type": "t",
            "item_id": 1695430975,
            "title": "Netbacks",
            "artist": "Duncan Gray",
        }

    def test_matches_url_ignoring_trailing_slash_and_scheme_case(self):
        result = lookup_item(
            "HTTPS://ticitaci.bandcamp.com/track/netbacks/",
            search=fake_search([TRACK_RESULT]),
        )
        assert result["item_id"] == 1695430975

    def test_picks_correct_result_among_several(self):
        other = dict(TRACK_RESULT, id=999, item_url_path="https://x.bandcamp.com/track/netbacks")
        result = lookup_item(TRACK_URL, search=fake_search([other, TRACK_RESULT]))
        assert result["item_id"] == 1695430975

    def test_raises_when_no_result_matches(self):
        with pytest.raises(BandcampError):
            lookup_item(TRACK_URL, search=fake_search([ALBUM_RESULT]))

    def test_raises_when_search_returns_nothing(self):
        with pytest.raises(BandcampError):
            lookup_item(TRACK_URL, search=fake_search([]))


class TestEmbedFromUrl:
    def test_builds_embed_for_track(self):
        html = embed_from_url(TRACK_URL, search=fake_search([TRACK_RESULT]))
        assert "track=1695430975/" in html
        assert ">Netbacks by Duncan Gray</a>" in html
        assert html.startswith("<iframe")

    def test_builds_embed_for_album(self):
        html = embed_from_url(ALBUM_URL, search=fake_search([ALBUM_RESULT]))
        assert "album=42/" in html
        assert "tracklist=true" in html

    def test_propagates_error_for_unresolvable_url(self):
        with pytest.raises(BandcampError):
            embed_from_url(TRACK_URL, search=fake_search([]))
