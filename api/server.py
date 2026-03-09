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
from db.database import init_db, get_db_session
import db.repository as repository

# ── Pydantic models ───────────────────────────────────────────────────────────
# ── App lifecycle ─────────────────────────────────────────────────────────────

_worker = BRAWorker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP PHASE
    log.info('"BRA server starting"')
    
    # Initialize DB (Sync call inside async wrapper is fine here)
    init_db() 
    
    # Start the background worker threads
    _worker.start()
    
    log.info('"BRA server ready"')
    
    yield  # <--- The server runs while it's "yielding" here
    
    # 2. SHUTDOWN PHASE
    log.info('"BRA server shutting down"')
    
    # Gracefully stop worker (drains the queue)
    _worker.stop()
    
    # Note: We do NOT call close_db() here because sync engines 
    # handle their own cleanup on process exit.
    
    log.info('"BRA server stopped"')

app = FastAPI(
    title="BRA API",
    lifespan=lifespan
)
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
