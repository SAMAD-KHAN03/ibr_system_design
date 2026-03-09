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

GET /health
    Liveness check.

Start
─────
    cd bra_system
    uvicorn api.server:app --reload --port 8000
"""

import sys
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Ensure bra_system root is importable regardless of working directory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from api.worker import BRAWorker, enqueue_job, get_job_status
from api.request_adapter import adapt_request


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
    # Start background worker on server startup
    _worker.start()
    yield
    # Stop worker on shutdown
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

    # Convert Pydantic models → plain dicts for adapter
    raw_body = body.model_dump()

    # adapt_request normalises age, pregnancy, indication, etc.
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
    """
    Poll for assessment result.

    Response shape
    ──────────────
    {
        "job_id":      "...",
        "status":      "queued" | "processing" | "done" | "failed",
        "queued_at":   "...",
        "started_at":  "...",
        "finished_at": "...",
        "result": {                          ← only present when status == "done"
            "patient_id":   "...",
            "patient_name": "...",
            "per_medication": {
                "Furosemide 40 MG Oral Tablet": {
                    "drug":      "...",
                    "condition": "...",
                    "ibr_report": {
                        "per_medicine": { ... },
                        "summary":      { favorable, conditional, unfavourable, overridden }
                    }
                },
                ...
            },
            "summary": {
                "favorable":   [...],
                "conditional": [...],
                "unfavourable":[...],
                "overridden":  [...],
                "errored":     [...]
            }
        },
        "error": "..."                       ← only present when status == "failed"
    }
    """
    status_entry = get_job_status(job_id)

    if status_entry.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return status_entry


@app.get("/assess/{job_id}/summary")
def get_assessment_summary(job_id: str):
    """
    Returns only the top-level summary (faster to parse for the frontend).
    Only meaningful when status == 'done'.
    """
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
