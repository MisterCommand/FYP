from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENTLENS_DB", str(tmp_path / "runs.sqlite3"))
    with TestClient(app) as client:
        yield client
