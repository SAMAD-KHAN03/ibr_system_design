"""
api/server.py

FastAPI server for the BRA system.

Endpoints
─────────
POST /assess
    Accepts the full patient + newMedications request body.
    Enqueues a job and immediately returns a job_id.
    The client polls GET /assess/{job_id} until status == "done".

GET /assess/{job_id}
    Returns current job status and result (once done).

GET /assess/{job_id}/summary
    Returns only the top-level summary (faster to parse for the frontend).

GET /reports
    Returns the most recent saved reports from Postgres (default: last 50).

GET /reports/{job_id}
    Fetches a single report directly from Postgres.

GET /health
    Liveness check.

Start
─────
    cd bra_system
    DATABASE_URL=postgresql://user:pass@localhost:5432/bra uvicorn api.server:app --reload --port 8000
"""

import sys
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from api.worker import BRAWorker, enqueue_job, get_job_status
from api.request_adapter import adapt_request
from api.db import init_db, fetch_report, fetch_recent_reports


# ── Pydantic request models ───────────────────────────────────────────────────

class Allergy(BaseModel):
    allergyName: str
    severity: Optional[str] = None
    notes: Optional[str] = None

class CurrentDiagnosis(BaseModel):
    name: str
    treatmentGiven: Optional[str] = None
    medicationName: Optional[str] = None

class PastMedicalCondition(BaseModel):
    conditionName: str
    dateOfDiagnosis: Optional[str] = None
    status: Optional[str] = "Active"
    treatmentGiven: Optional[str] = None
    details: Optional[str] = None
    stopDate: Optional[str] = None

class OngoingMedication(BaseModel):
    name: str
    dosage: Optional[str] = None
    type: Optional[str] = None
    indication: Optional[str] = None

class NewMedication(BaseModel):
    name: str
    dosage: Optional[str] = None
    type: Optional[str] = None

class AssessmentContext(BaseModel):
    assessmentDate: Optional[str] = None
    doctorId: Optional[str] = None
    doctorName: Optional[str] = None
    specialization: Optional[str] = None

class Patient(BaseModel):
    id: Optional[str] = None
    fullName: Optional[str] = None
    age: Optional[Any] = None
    gender: Optional[str] = None
    mrn: Optional[str] = None
    phoneNumber: Optional[str] = None
    isPregnant: Optional[bool] = False
    menstrualHistory: Optional[Any] = None
    chiefComplaint: Optional[str] = None
    currentDiagnosis: Optional[List[CurrentDiagnosis]] = []
    pastMedicalConditions: Optional[List[PastMedicalCondition]] = []
    allergies: Optional[List[Allergy]] = []
    lifestyleSocialHistory: Optional[str] = None
    familyHistory: Optional[str] = None
    ongoingMedications: Optional[List[OngoingMedication]] = []

class AssessRequest(BaseModel):
    patient: Patient
    newMedications: List[NewMedication] = Field(default_factory=list)
    assessmentContext: Optional[AssessmentContext] = None


# ── App lifecycle ─────────────────────────────────────────────────────────────

_worker = BRAWorker(num_threads=2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # create table if it doesn't exist (no-op if DB is down)
    _worker.start()
    yield
    _worker.stop()


app = FastAPI(
    title="BRA — Benefit Risk Assessment API",
    version="1.0.0",
    description="Queue-based iBR scoring per medicine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/assess", status_code=202)
def submit_assessment(body: AssessRequest):
    """
    Enqueues a BRA assessment job.
    Returns immediately with a job_id.
    Poll GET /assess/{job_id} to retrieve the result.
    """
    if not body.newMedications:
        raise HTTPException(status_code=400, detail="newMedications list is empty — nothing to assess.")

    raw_body = body.model_dump()
    patient_data, new_medications = adapt_request(raw_body)

    if not new_medications:
        raise HTTPException(status_code=400, detail="No valid medication names found in newMedications.")

    job_id = str(uuid.uuid4())

    job = {
        "job_id":             job_id,
        "patient_data":       patient_data,
        "new_medications":    new_medications,
        "assessment_context": raw_body.get("assessmentContext", {}),
        "submitted_at":       datetime.utcnow().isoformat(),
    }

    enqueue_job(job)

    return {
        "job_id":       job_id,
        "status":       "queued",
        "message":      f"Assessment queued for {len(new_medications)} medication(s). Poll GET /assess/{job_id} for results.",
        "medications":  [m["name"] for m in new_medications],
        "submitted_at": job["submitted_at"],
    }


@app.get("/assess/{job_id}")
def get_assessment(job_id: str):
    """Poll for assessment result (reads from in-memory store)."""
    status_entry = get_job_status(job_id)

    if status_entry.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return status_entry


@app.get("/assess/{job_id}/summary")
def get_assessment_summary(job_id: str):
    """Returns only the top-level summary. Only meaningful when status == 'done'."""
    status_entry = get_job_status(job_id)

    if status_entry.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if status_entry.get("status") != "done":
        return {"job_id": job_id, "status": status_entry["status"], "summary": None}

    result  = status_entry.get("result", {})
    summary = result.get("summary", {})

    return {
        "job_id":       job_id,
        "status":       "done",
        "patient_id":   result.get("patient_id"),
        "patient_name": result.get("patient_name"),
        "summary":      summary,
        "finished_at":  status_entry.get("finished_at"),
    }


# ── Postgres report endpoints ─────────────────────────────────────────────────

@app.get("/reports")
def list_reports(limit: int = Query(default=50, ge=1, le=500)):
    """
    Returns the most recent saved reports from Postgres.

    Query params:
        limit  — number of records to return (default 50, max 500)
    """
    rows = fetch_recent_reports(limit=limit)
    return {"count": len(rows), "reports": rows}


@app.get("/reports/{job_id}")
def get_report(job_id: str):
    """
    Fetches a single report directly from Postgres.
    Useful for retrieving results after the server has restarted
    (in-memory store is gone, but Postgres persists).
    """
    row = fetch_report(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No saved report found for job '{job_id}'.")
    return row
