"""Validation tests comparing generated output against reference validation/ directory.

These tests migrate the real flat-file data, generate HTML, and compare
against the known-good output in validation/. They verify that the rewrite
produces the same output as the original system.

Only slug-named release files are compared (not UUID-named ones, which have
the [[MASTERS]] bug in the original output for artist pages).
"""

import re
from pathlib import Path

import pytest

from mblabelsite.database import Database
from mblabelsite.generator import generate_all
from mblabelsite.migrate import migrate_all

PROJECT_ROOT = Path(__file__).parent.parent


def _is_uuid(name: str) -> bool:
    """Check if a filename looks like a UUID."""
    return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.html$", name))


@pytest.fixture(scope="module")
def generated_output(tmp_path_factory):
    """Migrate real data and generate output for comparison.

    This is module-scoped so it only runs once for all validation tests.
    """
    tmp_dir = tmp_path_factory.mktemp("validation")
    output_dir = tmp_dir / "output"
    output_dir.mkdir()

    data_dir = PROJECT_ROOT / "data"
    input_dir = PROJECT_ROOT / "input"
    template_dir = PROJECT_ROOT / "templates"
    validation_dir = PROJECT_ROOT / "validation"

    # Skip if validation data doesn't exist
    if not validation_dir.exists() or not data_dir.exists():
        pytest.skip("Validation data not available")

    # Copy cover art images to a temporary data_dir/covers/ for the generator
    tmp_data_dir = tmp_dir / "data"
    tmp_data_dir.mkdir()
    covers_src = validation_dir / "images" / "covers"
    covers_dst = tmp_data_dir / "covers"
    covers_dst.mkdir(parents=True, exist_ok=True)
    if covers_src.exists():
        for img in covers_src.iterdir():
            if img.is_file():
                (covers_dst / img.name).write_bytes(img.read_bytes())

    # Copy artist images to output
    artists_img_src = validation_dir / "images" / "artists"
    artists_img_dst = output_dir / "images" / "artists"
    artists_img_dst.mkdir(parents=True, exist_ok=True)
    if artists_img_src.exists():
        for img in artists_img_src.iterdir():
            if img.is_file():
                (artists_img_dst / img.name).write_bytes(img.read_bytes())

    # Create DB and migrate
    db_path = tmp_dir / "cache.db"
    db = Database(db_path)
    migrate_all(db, data_dir, input_dir)

    # Generate output
    for subdir in ["releases", "artists", "css"]:
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)

    generate_all(db, template_dir, input_dir, tmp_data_dir, output_dir)
    db.close()

    return output_dir


@pytest.fixture(scope="module")
def validation_dir():
    vdir = PROJECT_ROOT / "validation"
    if not vdir.exists():
        pytest.skip("Validation directory not available")
    return vdir


class TestReleaseValidation:
    """Compare slug-named release HTML files against validation/."""

    def _get_slug_release_files(self, validation_dir):
        """Get list of slug-named (non-UUID) release HTML files."""
        releases_dir = validation_dir / "releases"
        if not releases_dir.exists():
            return []
        return [
            f.name
            for f in releases_dir.iterdir()
            if f.is_file() and f.suffix == ".html" and not _is_uuid(f.name)
        ]

    def test_slug_release_files_exist(self, generated_output, validation_dir):
        """All slug-named release files from validation exist in generated output."""
        slug_files = self._get_slug_release_files(validation_dir)
        assert len(slug_files) > 0, "No slug-named release files found in validation"

        missing = []
        for fname in slug_files:
            gen_file = generated_output / "releases" / fname
            if not gen_file.exists():
                missing.append(fname)

        assert missing == [], f"Missing {len(missing)} release files: {missing[:10]}"

    def test_slug_release_content_matches(self, generated_output, validation_dir):
        """Content of slug-named release files matches validation."""
        slug_files = self._get_slug_release_files(validation_dir)
        mismatches = []

        for fname in slug_files:
            val_content = (validation_dir / "releases" / fname).read_text()
            gen_file = generated_output / "releases" / fname
            if not gen_file.exists():
                mismatches.append((fname, "MISSING"))
                continue
            gen_content = gen_file.read_text()
            if val_content != gen_content:
                mismatches.append((fname, "CONTENT_MISMATCH"))

        if mismatches:
            details = "\n".join(f"  {f}: {reason}" for f, reason in mismatches[:10])
            pytest.fail(
                f"{len(mismatches)} of {len(slug_files)} files differ:\n{details}"
            )


class TestHomepageValidation:
    """Compare generated index.html against validation/."""

    def test_homepage_exists(self, generated_output):
        assert (generated_output / "index.html").exists()

    def test_homepage_has_cover_art_links(self, generated_output):
        content = (generated_output / "index.html").read_text()
        assert "collage_images" in content
        assert "image_group" in content


class TestCoverArtValidation:
    """Verify cover art images exist."""

    def test_cover_images_exist(self, generated_output, validation_dir):
        val_covers = validation_dir / "images" / "covers"
        gen_covers = generated_output / "images" / "covers"

        if not val_covers.exists():
            pytest.skip("No validation cover art")

        val_files = {f.name for f in val_covers.iterdir() if f.is_file()}
        gen_files = {f.name for f in gen_covers.iterdir() if f.is_file()}

        missing = val_files - gen_files
        assert missing == set(), f"Missing cover images: {list(missing)[:10]}"
