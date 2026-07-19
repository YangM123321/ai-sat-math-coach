"""Focused regression coverage for per-session SQLite test-database
isolation (see tests/conftest.py's pytest_configure/pytest_unconfigure).

Deliberately does not spawn a nested pytest process to prove isolation
across two runs -- that would be slow and brittle. Instead this inspects
the real engine the already-running session built, which is enough to
catch a regression back to the old fixed, shared, repo-root path.
"""
import tempfile
from pathlib import Path

from app.db.session import engine

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_database_file_lives_under_the_system_temp_directory():
    db_path = Path(engine.url.database).resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    assert system_temp in db_path.parents


def test_database_filename_is_stable_and_clear():
    assert Path(engine.url.database).name == "test_sat_coach.db"


def test_no_database_file_is_created_in_the_repository_root():
    assert not (REPO_ROOT / "test_sat_coach.db").exists()
