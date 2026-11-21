from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app


@pytest.fixture(autouse=True)
def local_security_environment(monkeypatch):
    for name in ("EVENTLENS_API_TOKEN", "EVENTLENS_ALLOW_UNAUTHENTICATED", "API_HOST", "WEB_HOST"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENTLENS_DB", str(tmp_path / "runs.sqlite3"))
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000)) as client:
        yield client
