"""Tests for slug computation and filename sanitization."""



from mblabelsite.slug import get_artist_slug, get_release_slug, sanitize_filename


class TestSanitizeFilename:
    def test_lowercase(self):
        assert sanitize_filename("Hello World") == "hello-world"

    def test_replace_spaces(self):
        assert sanitize_filename("hello world") == "hello-world"

    def test_remove_invalid_chars(self):
        assert sanitize_filename('a/b\\c:d*e?"f<g>h|i') == "abcdefghi"

    def test_collapse_hyphens(self):
        assert sanitize_filename("a--b---c") == "a-b-c"

    def test_strip_hyphens(self):
        assert sanitize_filename("-hello-") == "hello"

    def test_complex_name(self):
        assert sanitize_filename("Duncan Gray") == "duncan-gray"

    def test_name_with_special_chars(self):
        assert (
            sanitize_filename("May Your Toes Kiss The Sand Again")
            == "may-your-toes-kiss-the-sand-again"
        )


class TestGetReleaseSlug:
    def test_computed_slug(self):
        slug = get_release_slug("some-id", "Duncan Gray", "Test Track")
        assert slug == "duncan-gray-test-track"

    def test_rewrite_from_file(self, tmp_path):
        rewrites = tmp_path / "rewrites"
        rewrites.mkdir()
        (rewrites / "release-123.rewrite").write_text("custom-slug\n")
        slug = get_release_slug("release-123", "Artist", "Title", input_dir=tmp_path)
        assert slug == "custom-slug"

    def test_fallback_when_no_rewrite(self, tmp_path):
        rewrites = tmp_path / "rewrites"
        rewrites.mkdir()
        slug = get_release_slug(
            "release-456", "Some Artist", "Some Title", input_dir=tmp_path
        )
        assert slug == "some-artist-some-title"

    def test_no_input_dir(self):
        slug = get_release_slug("id", "Artist", "Title", input_dir=None)
        assert slug == "artist-title"


class TestGetArtistSlug:
    def test_computed_slug(self):
        slug = get_artist_slug("some-id", "Duncan Gray")
        assert slug == "duncan-gray"

    def test_rewrite_from_file(self, tmp_path):
        rewrites = tmp_path / "artist_rewrites"
        rewrites.mkdir()
        (rewrites / "artist-123.rewrite").write_text("custom-artist\n")
        slug = get_artist_slug("artist-123", "Real Name", input_dir=tmp_path)
        assert slug == "custom-artist"

    def test_fallback_when_no_rewrite(self, tmp_path):
        rewrites = tmp_path / "artist_rewrites"
        rewrites.mkdir()
        slug = get_artist_slug("artist-456", "Some Artist", input_dir=tmp_path)
        assert slug == "some-artist"
