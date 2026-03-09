"""
api/server.py
=============
Synchronous Production FastAPI server.
"""

from __future__ import annotations
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Internal imports
from api.worker import BRAWorker, enqueue_job, get_job_status
from api.request_adapter import adapt_request
from db.database import init_db, get_db_session
import db.repository as repository

# ── Pydantic Models ──────────────────────────────────────────────────────────
# (Kept identical to your previous version for compatibility)
class Allergy(BaseModel):
    allergyName: str
    severity: Optional[str] = None
class CurrentDiagnosis(BaseModel):
    name: str
class PastMedicalCondition(BaseModel):
    conditionName: str
class OngoingMedication(BaseModel):
    name: str
class NewMedication(BaseModel):
    name: str
class AssessmentContext(BaseModel):
    doctorName: Optional[str] = None
    assessmentDate: Optional[str] = None
class Patient(BaseModel):
    id: Optional[str] = None
    fullName: Optional[str] = None
    ongoingMedications: List[OngoingMedication] = []
class AssessRequest(BaseModel):
    patient: Patient
    newMedications: List[NewMedication] = Field(default_factory=list)
    assessmentContext: Optional[AssessmentContext] = None

# ── App Lifecycle ─────────────────────────────────────────────────────────────

_worker = BRAWorker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("BRA server starting (Sync Mode)")
    init_db()  # Synchronous table creation
    _worker.start()
    yield
    _worker.stop()
    logging.info("BRA server stopped")

# ── App Definition ────────────────────────────────────────────────────────────

app = FastAPI(
    title="BRA — Benefit Risk Assessment API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Health Routes (Synchronous) ──────────────────────────────────────────────

@app.get("/health/live", tags=["Health"])
def liveness():
    return {"status": "live", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/health/ready", tags=["Health"])
def readiness():
    try:
        from sqlalchemy import text
        with get_db_session() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable")

# ── Assessment Routes (Synchronous) ──────────────────────────────────────────

@app.post("/assess", status_code=202, tags=["Assessment"])
def submit_assessment(body: AssessRequest):
    """
    Submit a job. FastAPI runs this sync function in a threadpool automatically.
    """
    if not body.newMedications:
        raise HTTPException(status_code=400, detail="newMedications is empty.")

    raw_body = body.model_dump()
    patient_data, new_medications = adapt_request(raw_body)

    job_id = str(uuid.uuid4())
    queued_at = datetime.now(timezone.utc)
    ctx = raw_body.get("assessmentContext") or {}

    # Synchronous DB Write
    with get_db_session() as db:
        repository.create_job(
            db,
            job_id=job_id,
            patient_id=patient_data.get("id", ""),
            patient_name=patient_data.get("fullName", ""),
            doctor_name=ctx.get("doctorName", ""),
            assessment_date=ctx.get("assessmentDate", ""),
            queued_at=queued_at,
        )

    # In-memory queue handover
    enqueue_job({
        "job_id": job_id,
        "patient_data": patient_data,
        "new_medications": new_medications,
        "assessment_context": ctx,
    })

    return {"job_id": job_id, "status": "queued"}

@app.get("/assess/{job_id}", tags=["Assessment"])
def get_assessment(job_id: str):
    """Poll for job status from cache/DB."""
    status_entry = get_job_status(job_id)
    if status_entry.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found.")
    return status_entry

# ── Report Routes (Synchronous) ───────────────────────────────────────────────

@app.get("/reports/{job_id}", tags=["Reports"])
def get_report(job_id: str):
    """Fetch full report directly from DB."""
    with get_db_session() as db:
        job = repository.get_job_with_report(db, job_id)
        
    if not job:
        raise HTTPException(status_code=404, detail="Report not found.")
        
    return {
        "job_id": job.id,
        "status": job.status,
        "patient_name": job.patient_name,
        "report": job.report.report_json if job.report else None
    }