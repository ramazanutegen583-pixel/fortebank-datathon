"""Local durable job state. Each operation owns its SQLite connection."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


def failed_response(job_id: str, code: str, message: str) -> dict:
    return {"job_id": job_id, "status": "failed", "error": {"code": code, "message": message}}


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at REAL NOT NULL,
                deadline REAL NOT NULL, response TEXT NOT NULL, details TEXT,
                completed_at REAL
            )""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, job_id: str, created_at: float, deadline: float) -> None:
        response = {"job_id": job_id, "status": "processing"}
        with self.connect() as db:
            db.execute("INSERT INTO jobs(id,status,created_at,deadline,response) VALUES(?,?,?,?,?)",
                       (job_id, "processing", created_at, deadline, json.dumps(response)))

    def get(self, job_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["response"] = json.loads(result["response"])
        result["details"] = json.loads(result["details"]) if result["details"] else None
        return result

    def finish(self, job_id: str, response: dict, details: dict | None = None) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status=?,response=?,details=?,completed_at=? WHERE id=? AND status='processing'",
                (response["status"], json.dumps(response, allow_nan=False),
                 json.dumps(details, allow_nan=False) if details is not None else None, time.time(), job_id),
            )
        return cursor.rowcount == 1

    def fail(self, job_id: str, code: str, message: str) -> bool:
        return self.finish(job_id, failed_response(job_id, code, message))

    def recover(self) -> None:
        with self.connect() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM jobs WHERE status='processing'")]
        for job_id in ids:
            self.fail(job_id, "SERVICE_RESTARTED", "The service restarted before processing completed. Please submit again.")

    def expire(self) -> None:
        with self.connect() as db:
            ids = [row[0] for row in db.execute(
                "SELECT id FROM jobs WHERE status='processing' AND deadline<=?", (time.time(),))]
        for job_id in ids:
            self.fail(job_id, "TIMEOUT", "The processing deadline was exceeded. Please try a shorter video or reduce the queue.")
