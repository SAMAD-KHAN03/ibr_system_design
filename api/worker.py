from __future__ import annotations

import logging
import os
import queue
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from db.database import get_db_session
from db import repository

log = logging.getLogger(__name__)

# --- Shared State ---
job_queue: queue.Queue = queue.Queue()
# job_id → full status dict (Hot cache for recent jobs)
results_store: Dict[str, Dict[str, Any]] = {}
_store_lock = threading.Lock()

STATUS_QUEUED     = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE       = "done"
STATUS_FAILED     = "failed"

_NUM_THREADS = int(os.environ.get("WORKER_THREADS", "2"))

# --- Public Interface ---

def enqueue_job(job: Dict[str, Any]) -> None:
    """
    Update in-memory cache and add to execution queue.
    Database record is already created by server.py to avoid IntegrityErrors.
    """
    job_id = job["job_id"]
    submitted_at = job.get("submitted_at") or datetime.now(timezone.utc).isoformat()

    status_entry = {
        "status": STATUS_QUEUED,
        "job_id": job_id,
        "result": None,
        "error": None,
        "queued_at": submitted_at,
        "started_at": None,
        "finished_at": None,
    }

    with _store_lock:
        results_store[job_id] = status_entry

    job_queue.put(job)
    log.info("job_enqueued_in_memory job_id=%s", job_id)

def get_job_status(job_id: str) -> Dict[str, Any]:
    """Retrieves status from cache or falls back to DB on cache miss."""
    with _store_lock:
        cached = results_store.get(job_id)
    if cached:
        return cached

    log.info("cache_miss job_id=%s — querying DB", job_id)
    try:
        with get_db_session() as session:
            job = repository.get_job_with_report(session, job_id)
            if not job:
                return {"status": "not_found", "job_id": job_id}
            
            entry = {
                "status": job.status,
                "job_id": job_id,
                "result": job.report.report_json if job.report else None,
                "error": job.error_message,
                "queued_at": job.queued_at.isoformat() if job.queued_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            with _store_lock:
                results_store[job_id] = entry
            return entry
    except Exception:
        log.exception("db_fetch_status_failed job_id=%s", job_id)
        return {"status": "not_found", "job_id": job_id}

# --- Internal Processor ---

def _process_job(job: Dict[str, Any]) -> None:
    """
    Runs assessment logic and updates DB/Cache status to processing -> done/failed.
    """
    from bra_assessor import assess
    job_id = job["job_id"]
    started_at = datetime.now(timezone.utc)

    # 1. Update In-Memory Cache to Processing
    with _store_lock:
        if job_id in results_store:
            results_store[job_id]["status"] = STATUS_PROCESSING
            results_store[job_id]["started_at"] = started_at.isoformat()

    # 2. Update DB to Processing
    try:
        with get_db_session() as session:
            repository.mark_job_processing(session, job_id, started_at)

        # 3. Run BRA assessment
        log.info("job_started job_id=%s", job_id)
        report = assess(patient_data=job["patient_data"], new_medications=job["new_medications"])

        # 4. Build Final Result
        finished_at = datetime.now(timezone.utc)
        final_result = {
            "job_id": job_id,
            "patient_name": job["patient_data"].get("fullName", ""),
            "summary": _build_summary(report.get("per_medicine", {})),
            "per_medication": report.get("per_medicine", {}),
        }

        # 5. Save Done state to Cache and DB
        with _store_lock:
            if job_id in results_store:
                results_store[job_id].update({
                    "status": STATUS_DONE,
                    "result": final_result,
                    "finished_at": finished_at.isoformat()
                })
        
        with get_db_session() as session:
            repository.save_report(session, job_id, final_result)
            repository.mark_job_done(session, job_id, finished_at)

        log.info("job_done job_id=%s", job_id)

    except Exception as exc:
        log.exception("job_failed job_id=%s", job_id)
        finished_at = datetime.now(timezone.utc)
        err_msg = traceback.format_exc()
        
        with _store_lock:
            if job_id in results_store:
                results_store[job_id].update({
                    "status": STATUS_FAILED,
                    "error": str(exc),
                    "finished_at": finished_at.isoformat()
                })
        
        with get_db_session() as session:
            repository.mark_job_failed(session, job_id, err_msg, finished_at)

def _build_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregates outcomes for the summary report."""
    favorable = [k for k, v in results.items() if v.get("ibr_outcome") == "Favorable"]
    unfavourable = [k for k, v in results.items() if v.get("halted") or v.get("ibr_outcome") == "Unfavourable"]
    conditional = [k for k, v in results.items() if v.get("ibr_outcome") == "Conditional"]
    
    return {
        "favorable": favorable,
        "conditional": conditional,
        "unfavourable": unfavourable,
        "count": len(results)
    }

# --- Worker Orchestration ---

class BRAWorker:
    def __init__(self, num_threads: int = _NUM_THREADS):
        self._num_threads = num_threads
        self._running = False
        self._semaphore = threading.Semaphore(num_threads)

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="bra-worker-loop").start()
        log.info("worker_started threads=%d", self._num_threads)

    def stop(self) -> None:
        self._running = False
        log.info("worker_stopping")

    def _loop(self) -> None:
        while self._running:
            try:
                job = job_queue.get(timeout=1)
                self._semaphore.acquire()
                threading.Thread(target=self._run_wrapper, args=(job,), daemon=True).start()
            except queue.Empty:
                continue

    def _run_wrapper(self, job):
        try:
            _process_job(job)
        except Exception:
            log.exception("worker_unhandled_error")
        finally:
            self._semaphore.release()
            job_queue.task_done()