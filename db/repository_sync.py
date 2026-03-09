from sqlalchemy.orm import Session
from db.models import AssessmentJob, AssessmentReport
import datetime

def mark_job_done_sync(session: Session, job_id: str, finished_at: datetime):
    job = session.query(AssessmentJob).filter_by(id=job_id).first()
    if job:
        job.status = "done"
        job.finished_at = finished_at
    session.commit()
def save_report_sync(session: Session, job_id: str, report: Dict[str, Any]):
    summary = report.get("summary", {})
    db_report = AssessmentReport(
        job_id=job_id,
        report_json=report,
        total_medications=len(report.get("per_medication", {})),
        favorable_count=len(summary.get("favorable", [])),
        conditional_count=len(summary.get("conditional", [])),
        unfavourable_count=len(summary.get("unfavourable", [])),
        overridden_count=len(summary.get("joverridden", []))
    )
    session.add(db_report)
    session.commit() # Sync commit
    return db_report