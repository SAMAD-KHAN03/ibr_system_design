"""
api/server.py
=============
Production FastAPI server for the BRA system.

Production additions over dev version
──────────────────────────────────────
1.  PostgreSQL persistence  — jobs and reports saved via db/repository.py
2.  Structured JSON logging — every request logged with job_id, duration, status
3.  Rate limiting           — slowapi (100 req/min per IP on POST /assess)
4.  Request ID middleware   — X-Request-ID header on every response
5.  Correlation logging     — request_id threaded through all log lines
6.  Graceful shutdown       — worker drains queue before process exits
7.  /health/live + /health/ready — separate liveness and readiness probes
                                   (readiness checks DB connectivity)
8.  GET /reports/{job_id}  — fetch historical report directly from DB
                             (survives server restart unlike in-memory cache)
9.  Global exception handler — never leaks stack traces to clients
10. CORS locked to APP_ORIGINS env var in production

Start (EC2 / production)
────────────────────────
    gunicorn api.server:app \
        --workers 1 \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -

NOTE: Use exactly 1 Gunicorn worker per instance because the in-process job
queue and results_store are not shared across OS processes. To run multiple
workers, migrate queue → SQS/Redis first.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Logging — JSON-structured, goes to stdout (captured by CloudWatch on EC2)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports from project
# ---------------------------------------------------------------------------

import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from api.worker import BRAWorker, enqueue_job, get_job_status
from api.request_adapter import adapt_request
from db.database import init_db, close_db, get_db_session
from db import repository

# ---------------------------------------------------------------------------
# Rate limiter (slowapi — wraps limits around routes declaratively)
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class Allergy(BaseModel):
    allergyName: str
    severity:    Optional[str] = None
    notes:       Optional[str] = None

class CurrentDiagnosis(BaseModel):
    name:            str
    treatmentGiven:  Optional[str] = None
    medicationName:  Optional[str] = None

class PastMedicalCondition(BaseModel):
    conditionName:     str
    dateOfDiagnosis:   Optional[str] = None
    status:            Optional[str] = "Active"
    treatmentGiven:    Optional[str] = None
    details:           Optional[str] = None
    stopDate:          Optional[str] = None

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
    id:                     Optional[str]                    = None
    fullName:               Optional[str]                    = None
    age:                    Optional[Any]                    = None
    gender:                 Optional[str]                    = None
    mrn:                    Optional[str]                    = None
    phoneNumber:            Optional[str]                    = None
    isPregnant:             Optional[bool]                   = False
    menstrualHistory:       Optional[Any]                    = None
    chiefComplaint:         Optional[str]                    = None
    currentDiagnosis:       Optional[List[CurrentDiagnosis]] = []
    pastMedicalConditions:  Optional[List[PastMedicalCondition]] = []
    allergies:              Optional[List[Allergy]]          = []
    lifestyleSocialHistory: Optional[str]                    = None
    familyHistory:          Optional[str]                    = None
    ongoingMedications:     Optional[List[OngoingMedication]] = []

class AssessRequest(BaseModel):
    patient:           Patient
    newMedications:    List[NewMedication] = Field(default_factory=list)
    assessmentContext: Optional[AssessmentContext] = None


# ---------------------------------------------------------------------------
# App lifecycle — DB init/teardown + worker start/stop
# ---------------------------------------------------------------------------

_worker = BRAWorker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    log.info('"BRA server starting"')
    await init_db()          # Creates tables if they don't exist (idempotent)
    _worker.start()
    log.info('"BRA server ready"')

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    log.info('"BRA server shutting down"')
    _worker.stop()           # Drain queue before exit
    await close_db()         # Release connection pool
    log.info('"BRA server stopped"')


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BRA — Benefit Risk Assessment API",
    version="1.0.0",
    description="Production iBR scoring service with PostgreSQL persistence",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiter error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — restrict to APP_ORIGINS in production
_origins_raw = os.environ.get("APP_ORIGINS", "*")
_origins = [o.strip() for o in _origins_raw.split(",")] if _origins_raw != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ---------------------------------------------------------------------------
# Middleware — Request ID + access log
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_id_and_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.perf_counter()

    response: Response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id

    log.info(
        '"method":"%s","path":"%s","status":%d,"duration_ms":%s,"request_id":"%s"',
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


# ---------------------------------------------------------------------------
# Global exception handler — never expose stack traces in production
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    log.exception('"unhandled_error","request_id":"%s"', request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error":      "Internal server error",
            "request_id": request_id,
        },
    )


# ---------------------------------------------------------------------------
# Health probes
# EC2 ALB target group should point to /health/ready
# ---------------------------------------------------------------------------

@app.get("/health/live", tags=["Health"])
async def liveness():
    """Liveness probe — always returns 200 if process is running."""
    return {"status": "live", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/health/ready", tags=["Health"])
async def readiness(db: AsyncSession = Depends(get_db_session)):
    """
    Readiness probe — checks DB connectivity.
    Returns 503 if DB is unreachable so ALB stops routing traffic here.
    """
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        log.error('"db_unreachable": "%s"', str(exc))
        raise HTTPException(status_code=503, detail="Database unavailable")


# ---------------------------------------------------------------------------
# POST /assess  — enqueue a job
# ---------------------------------------------------------------------------

@app.post("/assess", status_code=202, tags=["Assessment"])
@limiter.limit("100/minute")
async def submit_assessment(
    request: Request,           # required by slowapi
    body: AssessRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Enqueues a BRA assessment job.

    - Validates the request body
    - Persists a job row to PostgreSQL (status='queued')
    - Enqueues the job for background processing
    - Returns immediately with job_id for polling

    Rate limit: 100 requests / minute / IP
    """
    if not body.newMedications:
        raise HTTPException(
            status_code=400,
            detail="newMedications is empty — nothing to assess.",
        )

    raw_body = body.model_dump()
    patient_data, new_medications = adapt_request(raw_body)

    if not new_medications:
        raise HTTPException(
            status_code=400,
            detail="No valid medication names found in newMedications.",
        )

    job_id    = str(uuid.uuid4())
    queued_at = datetime.now(timezone.utc)
    ctx       = raw_body.get("assessmentContext") or {}

    # Persist job row immediately so GET /assess/{job_id} works right away
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

    job = {
        "job_id":             job_id,
        "patient_data":       patient_data,
        "new_medications":    new_medications,
        "assessment_context": ctx,
        "submitted_at":       queued_at.isoformat(),
    }

    enqueue_job(job)

    log.info(
        '"job_queued","job_id":"%s","patient_id":"%s","medications":%d',
        job_id, patient_data.get("id", ""), len(new_medications),
    )

    return {
        "job_id":       job_id,
        "status":       "queued",
        "message":      (
            f"Assessment queued for {len(new_medications)} medication(s). "
            f"Poll GET /assess/{job_id} for results."
        ),
        "medications":  [m["name"] for m in new_medications],
        "submitted_at": queued_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /assess/{job_id}  — poll job status + result
# ---------------------------------------------------------------------------

@app.get("/assess/{job_id}", tags=["Assessment"])
async def get_assessment(job_id: str):
    """
    Poll for assessment result.

    Reads from in-memory cache first (fast path for hot jobs).
    Falls back to PostgreSQL on cache miss (survives server restart).

    Response status values: queued | processing | done | failed
    """
    status_entry = get_job_status(job_id)

    if status_entry.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )

    return status_entry


# ---------------------------------------------------------------------------
# GET /assess/{job_id}/summary  — lightweight summary only
# ---------------------------------------------------------------------------

@app.get("/assess/{job_id}/summary", tags=["Assessment"])
async def get_assessment_summary(job_id: str):
    """
    Returns only the top-level summary for a completed job.
    Faster for the frontend to parse than the full result.
    """
    status_entry = get_job_status(job_id)

    if status_entry.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )

    if status_entry.get("status") != "done":
        return {
            "job_id": job_id,
            "status": status_entry["status"],
            "summary": None,
        }

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


# ---------------------------------------------------------------------------
# GET /reports/{job_id}  — fetch persisted report directly from DB
# Always works even after server restart (no cache dependency)
# ---------------------------------------------------------------------------

@app.get("/reports/{job_id}", tags=["Reports"])
async def get_report(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Fetches the full assessment report directly from PostgreSQL.
    Use this endpoint for historical lookups — it is not cache-dependent
    and works after server restarts.
    """
    job = await repository.get_job_with_report(db, job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Report for job '{job_id}' not found.")

    if job.status != "done":
        return {
            "job_id":  job_id,
            "status":  job.status,
            "report":  None,
            "message": f"Job is {job.status} — report not yet available.",
        }

    return {
        "job_id":       job_id,
        "status":       "done",
        "patient_id":   job.patient_id,
        "patient_name": job.patient_name,
        "finished_at":  job.finished_at.isoformat() if job.finished_at else None,
        "report":       job.report.report_json if job.report else None,
    }


# ---------------------------------------------------------------------------
# GET /reports/patient/{patient_id}  — all reports for a patient
# ---------------------------------------------------------------------------

@app.get("/reports/patient/{patient_id}", tags=["Reports"])
async def get_patient_reports(
    patient_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns all completed assessment jobs for a given patient_id.
    Useful for building a patient medication history view.
    """
    from sqlalchemy import select
    from db.models import AssessmentJob

    result = await db.execute(
        select(AssessmentJob)
        .where(
            AssessmentJob.patient_id == patient_id,
            AssessmentJob.status == "done",
        )
        .order_by(AssessmentJob.finished_at.desc())
        .limit(50)
    )
    jobs = result.scalars().all()

    if not jobs:
        raise HTTPException(
            status_code=404,
            detail=f"No completed assessments found for patient '{patient_id}'.",
        )

    return {
        "patient_id":   patient_id,
        "total":        len(jobs),
        "assessments": [
            {
                "job_id":         j.id,
                "doctor_name":    j.doctor_name,
                "specialization": j.specialization,
                "assessment_date":j.assessment_date,
                "finished_at":    j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
    }
