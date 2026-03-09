from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload
from db.models import AssessmentJob, AssessmentReport
from datetime import datetime
from typing import Any, Dict, Optional

def create_job(session: Session, job_id: str, **kwargs) -> AssessmentJob:
    job = AssessmentJob(id=job_id, status="queued", **kwargs)
    session.add(job)
    session.flush()
    return job

def mark_job_processing(session: Session, job_id: str, started_at: datetime):
    session.execute(
        update(AssessmentJob).where(AssessmentJob.id == job_id)
        .values(status="processing", started_at=started_at)
    )

def mark_job_done(session: Session, job_id: str, finished_at: datetime):
    session.execute(
        update(AssessmentJob).where(AssessmentJob.id == job_id)
        .values(status="done", finished_at=finished_at)
    )

def mark_job_failed(session: Session, job_id: str, error_message: str, finished_at: datetime):
    session.execute(
        update(AssessmentJob).where(AssessmentJob.id == job_id)
        .values(status="failed", error_message=error_message, finished_at=finished_at)
    )

def save_report(session: Session, job_id: str, report: Dict[str, Any]) -> AssessmentReport:
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
    session.flush()
    return db_report

def get_job_with_report(session: Session, job_id: str) -> Optional[AssessmentJob]:
    return session.execute(
        select(AssessmentJob).options(selectinload(AssessmentJob.report))
        .where(AssessmentJob.id == job_id)
    ).scalar_one_or_none()