import os
import sys

import pytest


# pytest_configure runs before test collection, which is the only point
# early enough to set DATABASE_URL: many test files import
# app.db.session at module level, and app/db/session.py builds its
# SQLAlchemy engine eagerly at first import -- a normal fixture (even a
# session-scoped autouse one) runs too late, since fixture bodies only
# execute at test setup, after collection has already imported
# app.db.session with whatever DATABASE_URL was in the environment.
#
# trylast=True is required: pytest's built-in tmpdir plugin sets
# config._tmp_path_factory in its own pytest_configure, and pluggy calls
# conftest hooks before unmarked builtin hooks by default -- without
# trylast, config._tmp_path_factory does not exist yet here.
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    os.environ["DIAGNOSTIC_PROVIDER"] = "rule_based"
    db_dir = config._tmp_path_factory.mktemp("db")
    database_path = db_dir / "test_sat_coach.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"


def pytest_unconfigure(config):
    session_module = sys.modules.get("app.db.session")
    if session_module is None:
        return

    engine = getattr(session_module, "engine", None)
    if engine is not None:
        engine.dispose()


@pytest.fixture(autouse=True)
def reset_db():
    from app.db.base import Base
    from app.db.session import engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
