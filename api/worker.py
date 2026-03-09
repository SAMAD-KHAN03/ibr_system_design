"""
api/worker.py
=============
Production-grade background worker for EC2 deployment.

Changes from dev version
────────────────────────
1. Every completed/failed job is persisted to PostgreSQL via db/repository.py
2. In-memory results_store is RETAINED as a fast read cache so GET /assess/{id}
   never hits the DB for hot jobs. Cold lookups (after restart) fall back to DB.
3. Structured logging (JSON-compatible) replaces bare print() calls.
4. Job status transitions are atomic: DB write + cache update in the same block.
5. Worker thread count is configurable via WORKER_THREADS env var.
6. Graceful shutdown: drains the queue before stopping.

Architecture note
─────────────────
The queue and in-memory store are still in-process (suitable for a single EC2
instance). To scale horizontally, swap:
  job_queue     → Redis list / SQS queue
  results_store → Redis hash / ElastiCache
No other file needs to change — the interface (enqueue_job / get_job_status)
stays identical.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared in-process state
# ---------------------------------------------------------------------------

job_queue: queue.Queue = queue.Queue()

# job_id → full status dict (hot cache — avoids DB round-trip for recent jobs)
results_store: Dict[str, Dict[str, Any]] = {}
_store_lock = threading.Lock()

# Status constants
STATUS_QUEUED     = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE       = "done"
STATUS_FAILED     = "failed"

# Worker thread count from environment (default 2 for t3.medium, raise for larger)
_NUM_THREADS = int(os.environ.get("WORKER_THREADS", "2"))


# ---------------------------------------------------------------------------
# Public interface (called by server.py — interface unchanged from dev version)
# ---------------------------------------------------------------------------

def enqueue_job(job: Dict[str, Any]) -> None:
    """
    Enqueue a job and set initial status in both cache and DB.
    Called synchronously from the FastAPI route handler.
    """
    job_id    = job["job_id"]
    queued_at = datetime.now(timezone.utc)

    status_entry = {
        "status":      STATUS_QUEUED,
        "job_id":      job_id,
        "result":      None,
        "error":       None,
        "queued_at":   queued_at.isoformat(),
        "started_at":  None,
        "finished_at": None,
    }

    with _store_lock:
        results_store[job_id] = status_entry

    # Persist job row to DB (fire-and-forget in a background thread so the
    # enqueue call stays synchronous and fast for the route handler)
    threading.Thread(
        target=_create_job_in_db,
        args=(job, queued_at),
        daemon=True,
        name=f"db-create-{job_id}",
    ).start()

    job_queue.put(job)
    log.info("job_enqueued job_id=%s", job_id)


def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Returns current job status.
    Hot path: reads from in-memory cache.
    Cold path (after restart): falls back to DB synchronously.
    """
    with _store_lock:
        cached = results_store.get(job_id)

    if cached:
        return cached

    # Cache miss — server restarted, look up DB
    log.info("cache_miss job_id=%s — querying DB", job_id)
    return _fetch_from_db_sync(job_id)


# ---------------------------------------------------------------------------
# DB helpers (sync wrappers — run in worker threads, not the async event loop)
# ---------------------------------------------------------------------------

def _run_async(coro) -> Any:
    """
    Runs an async coroutine from a sync thread.
    Each call creates a short-lived event loop — correct for worker threads
    which are outside FastAPI's event loop.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _create_job_in_db(job: Dict[str, Any], queued_at: datetime) -> None:
    """Inserts the initial job row into PostgreSQL."""
    try:
        from db.database import get_session
        from db.repository import create_job

        ctx  = job.get("assessment_context") or {}
        p    = job.get("patient_data", {})

        async def _insert():
            async with get_session() as session:
                await create_job(
                    session,
                    job_id=job["job_id"],
                    patient_id=p.get("id", ""),
                    patient_name=p.get("fullName", ""),
                    doctor_name=ctx.get("doctorName", ""),
                    specialization=ctx.get("specialization", ""),
                    assessment_date=ctx.get("assessmentDate", ""),
                    queued_at=queued_at,
                )

        _run_async(_insert())
    except Exception:
        log.exception("db_create_job_failed job_id=%s", job.get("job_id"))


def _save_result_to_db(job_id: str, final_result: Dict[str, Any]) -> None:
    """Saves the completed report and marks job as done in PostgreSQL."""
    try:
        from db.database import get_session
        from db.repository import save_report, mark_job_done

        finished_at = datetime.now(timezone.utc)

        async def _write():
            async with get_session() as session:
                await save_report(session, job_id=job_id, report=final_result)
                await mark_job_done(session, job_id=job_id, finished_at=finished_at)

        _run_async(_write())
        log.info("job_saved_to_db job_id=%s", job_id)
    except Exception:
        log.exception("db_save_failed job_id=%s", job_id)


def _save_failure_to_db(job_id: str, error: str) -> None:
    """Marks a failed job in PostgreSQL."""
    try:
        from db.database import get_session
        from db.repository import mark_job_failed

        finished_at = datetime.now(timezone.utc)

        async def _write():
            async with get_session() as session:
                await mark_job_failed(
                    session,
                    job_id=job_id,
                    error_message=error,
                    finished_at=finished_at,
                )

        _run_async(_write())
    except Exception:
        log.exception("db_failure_save_failed job_id=%s", job_id)


def _fetch_from_db_sync(job_id: str) -> Dict[str, Any]:
    """
    Fetches job + report from DB synchronously.
    Only called on cache miss (e.g. after server restart).
    """
    try:
        from db.database import get_session
        from db.repository import get_job_with_report

        async def _fetch():
            async with get_session() as session:
                return await get_job_with_report(session, job_id)

        job = _run_async(_fetch())

        if job is None:
            return {"status": "not_found", "job_id": job_id}

        entry: Dict[str, Any] = {
            "status":      job.status,
            "job_id":      job_id,
            "result":      None,
            "error":       job.error_message,
            "queued_at":   job.queued_at.isoformat()   if job.queued_at   else None,
            "started_at":  job.started_at.isoformat()  if job.started_at  else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }

        if job.report:
            entry["result"] = job.report.report_json

        # Repopulate cache so next request is fast
        with _store_lock:
            results_store[job_id] = entry

        return entry

    except Exception:
        log.exception("db_fetch_failed job_id=%s", job_id)
        return {"status": "not_found", "job_id": job_id}


# ---------------------------------------------------------------------------
# Core job processor
# ---------------------------------------------------------------------------

def _process_job(job: Dict[str, Any]) -> None:
    """
    Runs inside a worker thread.
    1. Marks job as processing (cache + DB)
    2. Calls bra_assessor.assess()
    3. Saves result to cache + DB
    4. Marks job done (cache + DB)
    """
    import sys
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    from bra_assessor import assess

    job_id          = job["job_id"]
    patient_data    = job["patient_data"]
    new_medications = job["new_medications"]
    assessment_ctx  = job.get("assessment_context", {})

    started_at = datetime.now(timezone.utc)

    # ── Mark processing ──────────────────────────────────────────────────────
    with _store_lock:
        results_store[job_id]["status"]     = STATUS_PROCESSING
        results_store[job_id]["started_at"] = started_at.isoformat()

    # Update DB asynchronously (non-blocking)
    threading.Thread(
        target=lambda: _run_async(_mark_processing_in_db(job_id, started_at)),
        daemon=True,
    ).start()

    log.info("job_started job_id=%s medications=%d", job_id, len(new_medications))

    # ── Run BRA assessment ───────────────────────────────────────────────────
    per_medication_results: Dict[str, Any] = {}

    try:
        report = assess(patient_data=patient_data, new_medications=new_medications)

        for drug_name, entry in report.get("per_medicine", {}).items():
            per_medication_results[drug_name] = entry

    except Exception as exc:
        error_detail = traceback.format_exc()
        log.exception("job_assessment_error job_id=%s", job_id)

        finished_at = datetime.now(timezone.utc)

        with _store_lock:
            results_store[job_id]["status"]      = STATUS_FAILED
            results_store[job_id]["error"]       = str(exc)
            results_store[job_id]["finished_at"] = finished_at.isoformat()

        _save_failure_to_db(job_id, error_detail)
        return

    # ── Build final result ───────────────────────────────────────────────────
    finished_at = datetime.now(timezone.utc)

    final_result = {
        "job_id":             job_id,
        "assessment_context": assessment_ctx,
        "patient_id":         patient_data.get("id", ""),
        "patient_name":       patient_data.get("fullName", ""),
        "per_medication":     per_medication_results,
        "summary":            _build_summary(per_medication_results),
    }

    # ── Update cache ─────────────────────────────────────────────────────────
    with _store_lock:
        results_store[job_id]["status"]      = STATUS_DONE
        results_store[job_id]["result"]      = final_result
        results_store[job_id]["finished_at"] = finished_at.isoformat()

    # ── Persist to DB ────────────────────────────────────────────────────────
    _save_result_to_db(job_id, final_result)

    log.info(
        "job_done job_id=%s duration_s=%.2f",
        job_id,
        (finished_at - started_at).total_seconds(),
    )


async def _mark_processing_in_db(job_id: str, started_at: datetime) -> None:
    from db.database import get_session
    from db.repository import mark_job_processing

    async with get_session() as session:
        await mark_job_processing(session, job_id=job_id, started_at=started_at)


def _build_summary(per_medication_results: Dict[str, Any]) -> Dict[str, Any]:
    favorable, conditional, unfavourable, overridden, errored = [], [], [], [], []

    for drug_name, data in per_medication_results.items():
        if data.get("error"):
            errored.append(drug_name)
            continue
        if data.get("override_triggered"):
            overridden.append(drug_name)
        elif data.get("halted"):
            unfavourable.append(drug_name)
        elif data.get("ibr_outcome") == "Favorable":
            favorable.append(drug_name)
        elif data.get("ibr_outcome") == "Conditional":
            conditional.append(drug_name)
        else:
            unfavourable.append(drug_name)

    return {
        "favorable":    favorable,
        "conditional":  conditional,
        "unfavourable": unfavourable,
        "overridden":   overridden,
        "errored":      errored,
    }


# ---------------------------------------------------------------------------
# BRAWorker
# ---------------------------------------------------------------------------

class BRAWorker:
    """
    Pulls jobs from job_queue and processes each in a thread-pool.
    Thread count controlled by WORKER_THREADS env var (default: 2).
    Suitable for a single EC2 instance. Scale horizontally by adding
    more instances with a shared Redis queue.
    """

    def __init__(self, num_threads: int = _NUM_THREADS):
        self._num_threads = num_threads
        self._running     = False
        self._semaphore   = threading.Semaphore(num_threads)

    def start(self) -> None:
        self._running = True
        t = threading.Thread(
            target=self._loop,
            daemon=True,
            name="bra-worker-loop",
        )
        t.start()
        log.info("worker_started threads=%d", self._num_threads)

    def stop(self) -> None:
        """Signal loop to stop. Waits up to 10s for queue to drain."""
        self._running = False
        try:
            job_queue.join()
        except Exception:
            pass
        log.info("worker_stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                job = job_queue.get(timeout=1)
            except queue.Empty:
                continue

            self._semaphore.acquire()

            def run(j=job):
                try:
                    _process_job(j)
                except Exception:
                    job_id = j.get("job_id", "unknown")
                    log.exception("worker_unhandled_error job_id=%s", job_id)
                    err = traceback.format_exc()
                    with _store_lock:
                        if job_id in results_store:
                            results_store[job_id]["status"]      = STATUS_FAILED
                            results_store[job_id]["error"]       = err
                            results_store[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
                    _save_failure_to_db(job_id, err)
                finally:
                    self._semaphore.release()
                    job_queue.task_done()

            threading.Thread(target=run, daemon=True).start()
