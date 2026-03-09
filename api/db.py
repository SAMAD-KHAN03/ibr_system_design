"""
api/db.py

Minimal Postgres persistence for BRA assessment reports.

Setup
─────
    pip install psycopg2-binary

Environment variable (required):
    DATABASE_URL  →  postgresql://user:password@host:5432/dbname

One table: assessment_reports
    job_id       TEXT PRIMARY KEY
    patient_id   TEXT
    patient_name TEXT
    status       TEXT
    result       JSONB
    error        TEXT
    queued_at    TIMESTAMPTZ
    started_at   TIMESTAMPTZ
    finished_at  TIMESTAMPTZ
"""

import os
import json
import logging
from typing import Any, Dict, Optional
# add these two lines at the very top of api/server.py, before any other imports
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

# ── Connection ────────────────────────────────────────────────────────────────

def get_connection():
    """Returns a new psycopg2 connection. Caller must close it."""
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(url)


# ── Schema ────────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS assessment_reports (
    job_id       TEXT PRIMARY KEY,
    patient_id   TEXT,
    patient_name TEXT,
    status       TEXT,
    result       JSONB,
    error        TEXT,
    queued_at    TIMESTAMPTZ,
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ
);
"""

def init_db() -> None:
    """Creates the table if it doesn't exist. Call once on startup."""
    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
        conn.close()
        logger.info("[DB] Table ready.")
    except Exception as exc:
        logger.warning(f"[DB] init_db failed (Postgres may be unavailable): {exc}")


# ── Upsert ────────────────────────────────────────────────────────────────────

UPSERT_SQL = """
INSERT INTO assessment_reports
    (job_id, patient_id, patient_name, status, result, error, queued_at, started_at, finished_at)
VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (job_id) DO UPDATE SET
    status      = EXCLUDED.status,
    result      = EXCLUDED.result,
    error       = EXCLUDED.error,
    started_at  = EXCLUDED.started_at,
    finished_at = EXCLUDED.finished_at;
"""

def save_report(job_entry: Dict[str, Any]) -> None:
    """
    Upserts a job_entry (the dict stored in results_store) into Postgres.
    Call this after the job finishes (status = done or failed).
    """
    result      = job_entry.get("result") or {}
    patient_id  = result.get("patient_id", "")
    patient_name= result.get("patient_name", "")

    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(UPSERT_SQL, (
                    job_entry.get("job_id"),
                    patient_id,
                    patient_name,
                    job_entry.get("status"),
                    json.dumps(result) if result else None,
                    job_entry.get("error"),
                    job_entry.get("queued_at"),
                    job_entry.get("started_at"),
                    job_entry.get("finished_at"),
                ))
        conn.close()
        logger.info(f"[DB] Saved report for job {job_entry.get('job_id')}.")
    except Exception as exc:
        logger.warning(f"[DB] save_report failed (non-fatal): {exc}")


# ── Fetch helpers ─────────────────────────────────────────────────────────────

def fetch_report(job_id: str) -> Optional[Dict[str, Any]]:
    """Returns the stored row as a dict, or None if not found."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_id, patient_id, patient_name, status, result, error, "
                "queued_at, started_at, finished_at FROM assessment_reports WHERE job_id = %s;",
                (job_id,)
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return _row_to_dict(row)
    except Exception as exc:
        logger.warning(f"[DB] fetch_report failed: {exc}")
        return None


def fetch_recent_reports(limit: int = 50) -> list:
    """Returns the most recent N reports (newest first)."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_id, patient_id, patient_name, status, result, error, "
                "queued_at, started_at, finished_at FROM assessment_reports "
                "ORDER BY queued_at DESC NULLS LAST LIMIT %s;",
                (limit,)
            )
            rows = cur.fetchall()
        conn.close()
        return [_row_to_dict(r) for r in rows]
    except Exception as exc:
        logger.warning(f"[DB] fetch_recent_reports failed: {exc}")
        return []


def _row_to_dict(row) -> Dict[str, Any]:
    keys = ["job_id", "patient_id", "patient_name", "status", "result",
            "error", "queued_at", "started_at", "finished_at"]
    d = dict(zip(keys, row))
    # psycopg2 returns JSONB as dict already; stringify timestamps
    for ts_key in ("queued_at", "started_at", "finished_at"):
        if d[ts_key] is not None:
            d[ts_key] = d[ts_key].isoformat()
    return d
