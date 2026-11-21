from datetime import datetime, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from analysis import SEED
from data import version


@contextmanager
def connection():
    path = os.environ.get("EVENTLENS_DB", str(Path(__file__).resolve().parent / "runs.sqlite3"))
    db = sqlite3.connect(path)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        with db:
            yield db
    finally:
        db.close()


def save(request, results):
    run = {"id": str(uuid4()), "request": request.model_dump(mode="json"), "results": results,
           "data_version": version(), "seed": SEED, "created_at": datetime.now(timezone.utc).isoformat()}
    with connection() as db:
        db.execute("INSERT INTO runs VALUES (?, ?)", (run["id"], json.dumps(run, allow_nan=False)))
    return run


def get(run_id):
    with connection() as db:
        row = db.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def all_runs():
    with connection() as db:
        rows = db.execute("SELECT payload FROM runs ORDER BY rowid DESC").fetchall()
    return [json.loads(row[0]) for row in rows]
