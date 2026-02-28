"""Tests for template loading."""

from mblabelsite.templates import load_release_template, load_template


class TestLoadTemplate:
    def test_load_existing_template(self, tmp_path):
        (tmp_path / "test_tpl").write_text("Hello [NAME]")
        result = load_template(tmp_path, "test_tpl")
        assert result == "Hello [NAME]"

    def test_load_nonexistent_template(self, tmp_path):
        result = load_template(tmp_path, "missing")
        assert result is None


class TestLoadReleaseTemplate:
    def test_default_release_template(self, tmp_path):
        (tmp_path / "template_release").write_text("default template")
        result = load_release_template(tmp_path, "some-id")
        assert result == "default template"

    def test_per_release_override(self, tmp_path):
        (tmp_path / "template_release").write_text("default template")
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        (releases_dir / "custom-id.template").write_text("custom template")
        result = load_release_template(tmp_path, "custom-id")
        assert result == "custom template"
