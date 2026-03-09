"""
api/worker.py

Queue-based background worker.

Flow:
  1. Server enqueues { job_id, patient_data, new_medications, context } → job_queue
  2. Worker.run() loops forever, pulling jobs from job_queue
  3. For each job: calls bra_assessor.assess() once per new_medication
  4. Stores result in results_store (shared dict, keyed by job_id)
  5. Persists final report to Postgres via api.db.save_report (non-fatal if DB is down)
  6. Server's GET /assess/{job_id} reads from results_store

The queue and results_store are plain Python objects — in-process for now.
To scale horizontally, swap them for Redis (queue → Redis list/stream,
results_store → Redis hash). No other file needs to change.
"""

import queue
import threading
import traceback
from datetime import datetime
from typing import Any, Dict

# ── Shared state (in-process) ─────────────────────────────────────────────────
job_queue: queue.Queue = queue.Queue()

# job_id → { status, result, error, started_at, finished_at }
results_store: Dict[str, Dict[str, Any]] = {}
_store_lock = threading.Lock()


# ── Status constants ──────────────────────────────────────────────────────────
STATUS_QUEUED     = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE       = "done"
STATUS_FAILED     = "failed"


def enqueue_job(job: Dict[str, Any]) -> None:
    """Called by the server to add a job. Updates results_store to 'queued'."""
    job_id = job["job_id"]
    with _store_lock:
        results_store[job_id] = {
            "status":      STATUS_QUEUED,
            "job_id":      job_id,
            "result":      None,
            "error":       None,
            "queued_at":   datetime.utcnow().isoformat(),
            "started_at":  None,
            "finished_at": None,
        }
    job_queue.put(job)


def get_job_status(job_id: str) -> Dict[str, Any]:
    """Called by the server's GET endpoint to check job status."""
    with _store_lock:
        return results_store.get(job_id, {"status": "not_found", "job_id": job_id})


def _process_job(job: Dict[str, Any]) -> None:
    """
    Core processing logic — runs inside the worker thread.
    Calls bra_assessor.assess() once per new_medication.
    """
    import sys, os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    from bra_assessor import assess
    from api.db import save_report

    job_id          = job["job_id"]
    patient_data    = job["patient_data"]
    new_medications = job["new_medications"]
    assessment_ctx  = job.get("assessment_context", {})

    # Mark as processing
    with _store_lock:
        results_store[job_id]["status"]     = STATUS_PROCESSING
        results_store[job_id]["started_at"] = datetime.utcnow().isoformat()

    per_medication_results = {}

    print(f"\n[Worker] job={job_id} | assessing {len(new_medications)} medication(s)...")

    try:
        report = assess(patient_data=patient_data, new_medications=new_medications)

        for drug_name, entry in report.get("per_medicine", {}).items():
            per_medication_results[drug_name] = entry

    except Exception as exc:
        print(f"[Worker] Error during assessment: {exc}")
        traceback.print_exc()
        for med in new_medications:
            per_medication_results[med["name"]] = {
                "drug":  med["name"],
                "error": str(exc),
            }

    final_result = {
        "job_id":             job_id,
        "assessment_context": assessment_ctx,
        "patient_id":         patient_data.get("id", ""),
        "patient_name":       patient_data.get("fullName", ""),
        "per_medication":     per_medication_results,
        "summary":            _build_summary(per_medication_results),
    }

    with _store_lock:
        results_store[job_id]["status"]      = STATUS_DONE
        results_store[job_id]["result"]      = final_result
        results_store[job_id]["finished_at"] = datetime.utcnow().isoformat()
        entry_snapshot = dict(results_store[job_id])   # copy while holding lock

    # ── Persist to Postgres (non-fatal) ───────────────────────────────────────
    save_report(entry_snapshot)

    print(f"[Worker] job={job_id} done.")


def _build_summary(per_medication_results: Dict[str, Any]) -> Dict[str, Any]:
    """Builds a quick-read summary from the flat per_medicine entries."""
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


class BRAWorker:
    """
    Background worker that processes jobs from job_queue.
    Each job runs in its own thread so the worker loop never blocks.
    """

    def __init__(self, num_threads: int = 2):
        self._num_threads = num_threads
        self._running     = False

    def start(self) -> None:
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name="bra-worker-loop")
        t.start()
        print(f"[Worker] Started with {self._num_threads} processing thread(s).")

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        semaphore = threading.Semaphore(self._num_threads)

        while self._running:
            try:
                job = job_queue.get(timeout=1)
            except queue.Empty:
                continue

            semaphore.acquire()

            def run(j=job):
                try:
                    _process_job(j)
                except Exception:
                    job_id = j.get("job_id", "unknown")
                    print(f"[Worker] Unhandled error in job {job_id}:")
                    traceback.print_exc()
                    with _store_lock:
                        if job_id in results_store:
                            results_store[job_id]["status"]      = STATUS_FAILED
                            results_store[job_id]["error"]       = traceback.format_exc()
                            results_store[job_id]["finished_at"] = datetime.utcnow().isoformat()
                        entry_snapshot = dict(results_store.get(job_id, {}))
                    # Still try to persist the failure
                    try:
                        from api.db import save_report
                        save_report(entry_snapshot)
                    except Exception:
                        pass
                finally:
                    semaphore.release()
                    job_queue.task_done()

            threading.Thread(target=run, daemon=True).start()
