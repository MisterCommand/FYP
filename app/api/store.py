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
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        if "title" not in {row[1] for row in db.execute("PRAGMA table_info(runs)")}:
            db.execute("ALTER TABLE runs ADD COLUMN title TEXT")
        with db:
            yield db
    finally:
        db.close()


def save(request, results):
    run = {"id": str(uuid4()), "request": request.model_dump(mode="json"), "results": results,
           "data_version": version(), "seed": SEED, "created_at": datetime.now(timezone.utc).isoformat()}
    with connection() as db:
        db.execute("INSERT INTO runs (id, payload) VALUES (?, ?)", (run["id"], json.dumps(run, allow_nan=False)))
    return {**run, "title": None}


def get(run_id):
    with connection() as db:
        row = db.execute("SELECT payload, title FROM runs WHERE id = ?", (run_id,)).fetchone()
    return {**json.loads(row[0]), "title": row[1]} if row else None


def all_runs():
    with connection() as db:
        rows = db.execute("SELECT payload, title FROM runs ORDER BY rowid DESC").fetchall()
    return [{**json.loads(row[0]), "title": row[1]} for row in rows]


def rename(run_id, title):
    with connection() as db:
        changed = db.execute("UPDATE runs SET title = ? WHERE id = ?", (title, run_id)).rowcount
        row = db.execute("SELECT payload, title FROM runs WHERE id = ?", (run_id,)).fetchone()
    return {**json.loads(row[0]), "title": row[1]} if changed else None


def delete(run_id):
    with connection() as db:
        return bool(db.execute("DELETE FROM runs WHERE id = ?", (run_id,)).rowcount)
