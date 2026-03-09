"""
api/server.py
=============
Production FastAPI server for the BRA system.
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

from dotenv import load_dotenv
load_dotenv()

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.worker import BRAWorker, enqueue_job, get_job_status
from api.request_adapter import adapt_request
from db.database import init_db, close_db, get_db_session
import db.repository as repository

# ── Pydantic models ───────────────────────────────────────────────────────────

class Allergy(BaseModel):
    allergyName: str
    severity:    Optional[str] = None
    notes:       Optional[str] = None

class CurrentDiagnosis(BaseModel):
    name:           str
    treatmentGiven: Optional[str] = None
    medicationName: Optional[str] = None

class PastMedicalCondition(BaseModel):
    conditionName:   str
    dateOfDiagnosis: Optional[str] = None
    status:          Optional[str] = "Active"
    treatmentGiven:  Optional[str] = None
    details:         Optional[str] = None
    stopDate:        Optional[str] = None

class OngoingMedication(BaseModel):
    name:       str
    dosage:     Optional[str] = None
    type:       Optional[str] = None
    indication: Optional[str] = None

class NewMedication(BaseModel):
    name:   str
    dosage: Optional[str] = None
    type:   Optional[str] = None

class AssessmentContext(BaseModel):
    assessmentDate: Optional[str] = None
    doctorId:       Optional[str] = None
    doctorName:     Optional[str] = None
    specialization: Optional[str] = None

class Patient(BaseModel):
    id:                     Optional[str]                        = None
    fullName:               Optional[str]                        = None
    age:                    Optional[Any]                        = None
    gender:                 Optional[str]                        = None
    mrn:                    Optional[str]                        = None
    phoneNumber:            Optional[str]                        = None
    isPregnant:             Optional[bool]                       = False
    menstrualHistory:       Optional[Any]                        = None
    chiefComplaint:         Optional[str]                        = None
    currentDiagnosis:       Optional[List[CurrentDiagnosis]]     = []
    pastMedicalConditions:  Optional[List[PastMedicalCondition]] = []
    allergies:              Optional[List[Allergy]]              = []
    lifestyleSocialHistory: Optional[str]                        = None
    familyHistory:          Optional[str]                        = None
    ongoingMedications:     Optional[List[OngoingMedication]]    = []

class AssessRequest(BaseModel):
    patient:           Patient
    newMedications:    List[NewMedication]          = Field(default_factory=list)
    assessmentContext: Optional[AssessmentContext]  = None

# ── App lifecycle ─────────────────────────────────────────────────────────────

_worker = BRAWorker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info('"BRA server starting"')
    await init_db()
    _worker.start()
    log.info('"BRA server ready"')
    yield
    log.info('"BRA server shutting down"')
    _worker.stop()
    await close_db()
    log.info('"BRA server stopped"')

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BRA — Benefit Risk Assessment API",
    version="1.0.0",
    description="Production iBR scoring service with PostgreSQL persistence",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

_origins_raw = os.environ.get("APP_ORIGINS", "*")
_origins = [o.strip() for o in _origins_raw.split(",")] if _origins_raw != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Middleware ────────────────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_and_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    log.info(
        '"method":"%s","path":"%s","status":%d,"duration_ms":%s,"request_id":"%s"',
        request.method, request.url.path, response.status_code, duration_ms, request_id,
    )
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    log.exception('"unhandled_error","request_id":"%s"', request_id)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": request_id},
    )

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health/live", tags=["Health"])
async def liveness():
    return {"status": "live", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/health/ready", tags=["Health"])
async def readiness(db: AsyncSession = Depends(get_db_session)):
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        log.error('"db_unreachable": "%s"', str(exc))
        raise HTTPException(status_code=503, detail="Database unavailable")

# ── POST /assess ──────────────────────────────────────────────────────────────

@app.post("/assess", status_code=202, tags=["Assessment"])
async def submit_assessment(
    body: AssessRequest,
    db: AsyncSession = Depends(get_db_session),
):
    if not body.newMedications:
        raise HTTPException(status_code=400, detail="newMedications is empty.")

    raw_body = body.model_dump()
    patient_data, new_medications = adapt_request(raw_body)

    if not new_medications:
        raise HTTPException(status_code=400, detail="No valid medication names found.")

    job_id    = str(uuid.uuid4())
    queued_at = datetime.now(timezone.utc)
    ctx       = raw_body.get("assessmentContext") or {}

    await repository.create_job(
        db,
        job_id=job_id,
        patient_id=patient_data.get("id", ""),
        patient_name=patient_data.get("fullName", ""),
        doctor_name=ctx.get("doctorName", ""),
        specialization=ctx.get("specialization", ""),
        assessment_date=ctx.get("assessmentDate", ""),
        queued_at=queued_at,
    )

    enqueue_job({
        "job_id":             job_id,
        "patient_data":       patient_data,
        "new_medications":    new_medications,
        "assessment_context": ctx,
        "submitted_at":       queued_at.isoformat(),
    })

    log.info('"job_queued","job_id":"%s","medications":%d', job_id, len(new_medications))

    return {
        "job_id":      job_id,
        "status":      "queued",
        "message":     f"Assessment queued for {len(new_medications)} medication(s). Poll GET /assess/{job_id} for results.",
        "medications": [m["name"] for m in new_medications],
        "submitted_at": queued_at.isoformat(),
    }

# ── GET /assess/{job_id} ──────────────────────────────────────────────────────

@app.get("/assess/{job_id}", tags=["Assessment"])
async def get_assessment(job_id: str):
    status_entry = get_job_status(job_id)
    if status_entry.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return status_entry

# ── GET /assess/{job_id}/summary ──────────────────────────────────────────────

@app.get("/assess/{job_id}/summary", tags=["Assessment"])
async def get_assessment_summary(job_id: str):
    status_entry = get_job_status(job_id)
    if status_entry.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if status_entry.get("status") != "done":
        return {"job_id": job_id, "status": status_entry["status"], "summary": None}
    result = status_entry.get("result", {})
    return {
        "job_id":       job_id,
        "status":       "done",
        "patient_id":   result.get("patient_id"),
        "patient_name": result.get("patient_name"),
        "summary":      result.get("summary", {}),
        "finished_at":  status_entry.get("finished_at"),
    }

# ── GET /reports/{job_id} ─────────────────────────────────────────────────────

@app.get("/reports/{job_id}", tags=["Reports"])
async def get_report(job_id: str, db: AsyncSession = Depends(get_db_session)):
    job = await repository.get_job_with_report(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Report for job '{job_id}' not found.")
    if job.status != "done":
        return {"job_id": job_id, "status": job.status, "report": None,
                "message": f"Job is {job.status} — report not yet available."}
    return {
        "job_id":       job_id,
        "status":       "done",
        "patient_id":   job.patient_id,
        "patient_name": job.patient_name,
        "finished_at":  job.finished_at.isoformat() if job.finished_at else None,
        "report":       job.report.report_json if job.report else None,
    }

# ── GET /reports/patient/{patient_id} ────────────────────────────────────────

@app.get("/reports/patient/{patient_id}", tags=["Reports"])
async def get_patient_reports(patient_id: str, db: AsyncSession = Depends(get_db_session)):
    from sqlalchemy import select
    from db.models import AssessmentJob

    result = await db.execute(
        select(AssessmentJob)
        .where(AssessmentJob.patient_id == patient_id, AssessmentJob.status == "done")
        .order_by(AssessmentJob.finished_at.desc())
        .limit(50)
    )
    jobs = result.scalars().all()

    if not jobs:
        raise HTTPException(status_code=404,
                            detail=f"No completed assessments found for patient '{patient_id}'.")
    return {
        "patient_id": patient_id,
        "total":      len(jobs),
        "assessments": [
            {
                "job_id":          j.id,
                "doctor_name":     j.doctor_name,
                "specialization":  j.specialization,
                "assessment_date": j.assessment_date,
                "finished_at":     j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
    }
