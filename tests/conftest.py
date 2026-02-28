import pathlib

import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture
def data_dir(project_root):
    return project_root / "data"


@pytest.fixture
def input_dir(project_root):
    return project_root / "input"


@pytest.fixture
def template_dir(project_root):
    return project_root / "templates"


@pytest.fixture
def validation_dir(project_root):
    return project_root / "validation"


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output directory for tests."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def tmp_db(tmp_path):
    """Temporary database path for tests."""
    return tmp_path / "cache.db"
