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
job_queue: queue.Queue = queue.Queue()
results_store: Dict[str, Dict[str, Any]] = {}
_store_lock = threading.Lock()

STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
_NUM_THREADS = int(os.environ.get("WORKER_THREADS", "2"))

def enqueue_job(job: Dict[str, Any]) -> None:
    job_id = job["job_id"]
    queued_at = datetime.now(timezone.utc)

    # Cache update
    status_entry = {
        "status": STATUS_QUEUED, "job_id": job_id, "result": None, "error": None,
        "queued_at": queued_at.isoformat(), "started_at": None, "finished_at": None,
    }
    with _store_lock:
        results_store[job_id] = status_entry

    # Sync DB Write
    try:
        with get_db_session() as session:
            ctx = job.get("assessment_context") or {}
            p = job.get("patient_data", {})
            repository.create_job(
                session, job_id=job_id, patient_id=p.get("id", ""),
                patient_name=p.get("fullName", ""), doctor_name=ctx.get("doctorName", ""),
                specialization=ctx.get("specialization", ""), assessment_date=ctx.get("assessmentDate", ""),
                queued_at=queued_at
            )
    except Exception:
        log.exception("Initial DB entry failed for job_id=%s", job_id)

    job_queue.put(job)

def _process_job(job: Dict[str, Any]) -> None:
    from bra_assessor import assess
    job_id = job["job_id"]
    started_at = datetime.now(timezone.utc)

    # 1. Update status to Processing
    with _store_lock:
        results_store[job_id]["status"] = STATUS_PROCESSING
        results_store[job_id]["started_at"] = started_at.isoformat()
    
    with get_db_session() as session:
        repository.mark_job_processing(session, job_id, started_at)

    try:
        # 2. Run Assessment
        report = assess(patient_data=job["patient_data"], new_medications=job["new_medications"])
        
        # 3. Build Final Result
        finished_at = datetime.now(timezone.utc)
        final_result = {
            "job_id": job_id,
            "patient_name": job["patient_data"].get("fullName", ""),
            "per_medication": report.get("per_medicine", {}),
            "summary": _build_summary(report.get("per_medicine", {})),
        }

        # 4. Save to Cache and DB
        with _store_lock:
            results_store[job_id].update({
                "status": STATUS_DONE, "result": final_result, "finished_at": finished_at.isoformat()
            })
        
        with get_db_session() as session:
            repository.save_report(session, job_id, final_result)
            repository.mark_job_done(session, job_id, finished_at)

    except Exception as exc:
        log.exception("Job failed job_id=%s", job_id)
        finished_at = datetime.now(timezone.utc)
        err_msg = traceback.format_exc()
        with _store_lock:
            results_store[job_id].update({
                "status": STATUS_FAILED, "error": str(exc), "finished_at": finished_at.isoformat()
            })
        with get_db_session() as session:
            repository.mark_job_failed(session, job_id, err_msg, finished_at)

def _build_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    # ... (Your existing _build_summary logic stays the same) ...
    return {"favorable": [], "unfavourable": []} # Simplified for brevity

class BRAWorker:
    def __init__(self, num_threads: int = _NUM_THREADS):
        self._num_threads = num_threads
        self._running = False
        self._semaphore = threading.Semaphore(num_threads)

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="bra-worker-loop").start()

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
        finally:
            self._semaphore.release()
            job_queue.task_done()