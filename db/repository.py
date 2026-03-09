from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AssessmentJob, AssessmentReport

log = logging.getLogger(__name__)


async def create_job(
    session: AsyncSession,
    *,
    job_id: str,
    patient_id: str,
    patient_name: str,
    doctor_name: str,
    specialization: str,
    assessment_date: str,
    queued_at: datetime,
) -> AssessmentJob:
    job = AssessmentJob(
        id=job_id,
        patient_id=patient_id,
        patient_name=patient_name,
        doctor_name=doctor_name,
        specialization=specialization,
        assessment_date=assessment_date,
        status="queued",
        queued_at=queued_at,
    )
    session.add(job)
    await session.flush()
    return job


async def mark_job_processing(session: AsyncSession, job_id: str, started_at: datetime) -> None:
    await session.execute(
        update(AssessmentJob).where(AssessmentJob.id == job_id)
        .values(status="processing", started_at=started_at)
    )


async def mark_job_done(session: AsyncSession, job_id: str, finished_at: datetime) -> None:
    await session.execute(
        update(AssessmentJob).where(AssessmentJob.id == job_id)
        .values(status="done", finished_at=finished_at)
    )


async def mark_job_failed(session: AsyncSession, job_id: str, error_message: str, finished_at: datetime) -> None:
    await session.execute(
        update(AssessmentJob).where(AssessmentJob.id == job_id)
        .values(status="failed", error_message=error_message, finished_at=finished_at)
    )


async def get_job(session: AsyncSession, job_id: str) -> Optional[AssessmentJob]:
    result = await session.execute(select(AssessmentJob).where(AssessmentJob.id == job_id))
    return result.scalar_one_or_none()


async def save_report(session: AsyncSession, *, job_id: str, report: Dict[str, Any]) -> AssessmentReport:
    summary = report.get("summary", {})
    db_report = AssessmentReport(
        job_id=job_id,
        report_json=report,
        total_medications=len(report.get("per_medication", {})),
        favorable_count=len(summary.get("favorable", [])),
        conditional_count=len(summary.get("conditional", [])),
        unfavourable_count=len(summary.get("unfavourable", [])),
        overridden_count=len(summary.get("overridden", [])),
    )
    session.add(db_report)
    await session.flush()
    return db_report


async def get_report(session: AsyncSession, job_id: str) -> Optional[AssessmentReport]:
    result = await session.execute(select(AssessmentReport).where(AssessmentReport.job_id == job_id))
    return result.scalar_one_or_none()


async def get_job_with_report(session: AsyncSession, job_id: str) -> Optional[AssessmentJob]:
    from sqlalchemy.orm import selectinload
    result = await session.execute(
        select(AssessmentJob)
        .options(selectinload(AssessmentJob.report))
        .where(AssessmentJob.id == job_id)
    )
    return result.scalar_one_or_none()