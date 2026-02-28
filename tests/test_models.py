"""Tests for data models."""

from mblabelsite.models import Artist, PurchaseLink, Release, Track


class TestTrack:
    def test_create_track(self):
        t = Track(position=1, title="Test Track", length_ms=300000)
        assert t.position == 1
        assert t.title == "Test Track"
        assert t.length_ms == 300000

    def test_default_length(self):
        t = Track(position=1, title="Test")
        assert t.length_ms == 0


class TestPurchaseLink:
    def test_create_purchase_link(self):
        p = PurchaseLink(store_name="Bandcamp", url="https://example.com", position=0)
        assert p.store_name == "Bandcamp"
        assert p.url == "https://example.com"
        assert p.position == 0


class TestRelease:
    def test_create_release(self):
        r = Release(
            id="abc-123",
            artist_credit="Test Artist",
            title="Test Title",
            date="2024-01-01",
        )
        assert r.id == "abc-123"
        assert r.artist_credit == "Test Artist"
        assert r.title == "Test Title"
        assert r.date == "2024-01-01"

    def test_default_lists_are_independent(self):
        """Verify that default list fields are not shared between instances."""
        r1 = Release(id="1", artist_credit="A", title="T", date="2024-01-01")
        r2 = Release(id="2", artist_credit="B", title="U", date="2024-01-02")
        r1.artist_ids.append("artist-1")
        assert r2.artist_ids == []

    def test_default_empty_strings(self):
        r = Release(id="1", artist_credit="A", title="T", date="2024-01-01")
        assert r.label == ""
        assert r.catno == ""
        assert r.artist_credit_phrase == ""
        assert r.slug == ""

    def test_cleanup_title_smart_quotes(self):
        r = Release(
            id="1",
            artist_credit="A",
            title="\u201cHello\u201d",
            date="2024-01-01",
        )
        r.cleanup_title()
        assert r.title == "&#8220;Hello&#8221;"

    def test_tracks_and_purchase_links(self):
        r = Release(
            id="1",
            artist_credit="A",
            title="T",
            date="2024-01-01",
            tracks=[Track(position=1, title="Song", length_ms=200000)],
            purchase_links=[
                PurchaseLink(store_name="Bandcamp", url="https://bc.com", position=0)
            ],
        )
        assert len(r.tracks) == 1
        assert len(r.purchase_links) == 1
        assert r.tracks[0].title == "Song"


class TestArtist:
    def test_create_artist(self):
        a = Artist(id="abc", name="Test Artist")
        assert a.id == "abc"
        assert a.name == "Test Artist"
        assert a.slug == ""

    def test_artist_with_slug(self):
        a = Artist(id="abc", name="Test Artist", slug="test-artist")
        assert a.slug == "test-artist"
