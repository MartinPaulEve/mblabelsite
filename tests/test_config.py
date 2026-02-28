"""Tests for config loading from pyproject.toml."""

import textwrap
from pathlib import Path
from unittest.mock import patch


class TestFindPyproject:
    def test_find_pyproject_returns_path(self):
        from mblabelsite.config import _find_pyproject

        result = _find_pyproject()
        assert result is not None
        assert result.name == "pyproject.toml"
        assert result.exists()

    def test_find_pyproject_returns_none_when_missing(self, tmp_path):
        from mblabelsite.config import _find_pyproject

        # Start from a directory with no pyproject.toml ancestors
        result = _find_pyproject(start=tmp_path / "deeply" / "nested" / "fake")
        assert result is None


class TestLoadToolConfig:
    def test_load_tool_config_returns_section(self):
        from mblabelsite.config import _load_tool_config

        config = _load_tool_config()
        assert isinstance(config, dict)
        assert "label_id" in config

    def test_load_tool_config_returns_empty_when_section_missing(self, tmp_path):
        from mblabelsite.config import _load_tool_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")
        config = _load_tool_config(pyproject)
        assert config == {}

    def test_load_tool_config_returns_empty_when_file_missing(self):
        from mblabelsite.config import _load_tool_config

        config = _load_tool_config(Path("/nonexistent/pyproject.toml"))
        assert config == {}


class TestConstantsLoadedFromPyproject:
    def test_label_id_matches_pyproject(self):
        import tomllib

        from mblabelsite.config import LABEL_ID

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        expected = data["tool"]["mblabelsite"]["label_id"]
        assert LABEL_ID == expected

    def test_site_url_matches_pyproject(self):
        import tomllib

        from mblabelsite.config import SITE_URL

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        expected = data["tool"]["mblabelsite"]["site_url"]
        assert SITE_URL == expected

    def test_excluded_release_ids_matches_pyproject(self):
        import tomllib

        from mblabelsite.config import EXCLUDED_RELEASE_IDS

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        expected = frozenset(data["tool"]["mblabelsite"]["excluded_release_ids"])
        assert EXCLUDED_RELEASE_IDS == expected

    def test_ignored_artist_ids_matches_pyproject(self):
        import tomllib

        from mblabelsite.config import IGNORED_ARTIST_IDS

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        expected = frozenset(data["tool"]["mblabelsite"]["ignored_artist_ids"])
        assert IGNORED_ARTIST_IDS == expected


class TestDefaultsWhenSectionMissing:
    def test_defaults_used_when_no_tool_section(self, tmp_path):
        """Write a pyproject.toml without [tool.mblabelsite] and verify fallback defaults."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "test"
            """)
        )

        import mblabelsite.config as config_mod

        with patch.object(
            config_mod, "_find_pyproject", return_value=pyproject
        ):
            # Re-execute module-level loading
            config = config_mod._load_tool_config(pyproject)

        assert config == {}

        # Verify the hardcoded defaults match original values
        assert config_mod._DEFAULTS["label_id"] == "62db3e96-423a-4e9d-bf66-7a017f1dfc73"
        assert config_mod._DEFAULTS["site_url"] == "https://ticitaci.com"
        assert config_mod._DEFAULTS["excluded_release_ids"] == [
            "14f0377a-dadf-4fb9-a141-4a6e8c9ed882"
        ]
        assert config_mod._DEFAULTS["ignored_artist_ids"] == [
            "8a26ca9b-d542-449b-a5e7-224da9eb8a77",
            "89ad4ac3-39f7-470e-963a-56509c546377",
        ]
