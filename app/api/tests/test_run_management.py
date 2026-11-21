import json
import sqlite3

import pytest

import store


def create_run(client):
    return client.post("/analyses", json={"holdings": [{"asset": "SPY", "weight": 1}]}).json()


def test_rename_and_delete(client):
    original = create_run(client)
    with store.connection() as db:
        payload = db.execute("SELECT payload FROM runs WHERE id = ?", (original["id"],)).fetchone()[0]
    url = f"/analyses/{original['id']}"
    renamed = client.patch(url, json={"title": "  September research  "})
    assert renamed.status_code == 200
    assert renamed.json() == {**original, "title": "September research"}
    assert client.get(f"/runs/{original['id']}").json() == renamed.json()
    assert client.get("/runs").json() == [renamed.json()]
    with store.connection() as db:
        assert db.execute("SELECT payload FROM runs WHERE id = ?", (original["id"],)).fetchone()[0] == payload
    assert client.patch(url, json={"title": "   "}).json()["title"] is None
    assert client.patch(url, json={"title": None}).status_code == 200
    assert client.delete(url).status_code == 204
    assert client.get("/runs").json() == []
    assert client.get(f"/runs/{original['id']}").status_code == 404
    assert client.delete(url).status_code == 404
    assert client.patch(url, json={"title": "Missing"}).status_code == 404


@pytest.mark.parametrize("body", [{}, {"title": 123}, {"title": "a" * 161}])
def test_title_validation(client, body):
    run = create_run(client)
    assert client.patch(f"/analyses/{run['id']}", json=body).status_code == 422
    assert client.get(f"/runs/{run['id']}").json() == run


def test_legacy_database_migration(client, tmp_path, monkeypatch):
    run = create_run(client)
    run.pop("title")
    path = tmp_path / "legacy.sqlite3"
    payload = json.dumps(run)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("INSERT INTO runs VALUES (?, ?)", (run["id"], payload))
    monkeypatch.setenv("EVENTLENS_DB", str(path))
    for _ in range(2):
        assert client.get("/runs").json() == [{**run, "title": None}]
    assert client.patch(f"/analyses/{run['id']}", json={"title": "Legacy research"}).status_code == 200
    with sqlite3.connect(path) as db:
        columns = {row[1]: row for row in db.execute("PRAGMA table_info(runs)")}
        assert columns["title"][3] == 0
        assert db.execute("SELECT payload, title FROM runs").fetchone() == (payload, "Legacy research")
    assert create_run(client)["title"] is None
    assert len(client.get("/runs").json()) == 2
