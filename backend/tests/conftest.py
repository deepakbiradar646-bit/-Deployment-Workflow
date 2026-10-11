from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEST_DB_DIR = tempfile.TemporaryDirectory(prefix="mlops-tests-")
os.environ["MLOPS_DATABASE_URL"] = f"sqlite:///{Path(TEST_DB_DIR.name) / 'test.db'}"

from app.database import Base, engine  # noqa: E402
from app.models import DeploymentEvent  # noqa: E402,F401


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def pytest_unconfigure(config):
    engine.dispose()
    TEST_DB_DIR.cleanup()
