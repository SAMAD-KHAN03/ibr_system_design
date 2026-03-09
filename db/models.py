"""
db/models.py
============
SQLAlchemy ORM models.

Tables
──────
assessment_jobs   — one row per job, tracks lifecycle + stores full JSON report
assessment_reports — one row per job (1-to-1), stores the final structured report
                     as JSONB for fast querying
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


# ---------------------------------------------------------------------------
# AssessmentJob
# Tracks the full job lifecycle. Mirrors the in-memory results_store schema.
# ---------------------------------------------------------------------------

class AssessmentJob(Base):
    __tablename__ = "assessment_jobs"

    # Primary key — same UUID generated in server.py before enqueue
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, nullable=False
    )

    # Patient identifiers (denormalised for fast lookup without JSON parsing)
    patient_id: Mapped[Optional[str]]   = mapped_column(String(128), nullable=True, index=True)
    patient_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Doctor / context
    doctor_name: Mapped[Optional[str]]     = mapped_column(String(256), nullable=True)
    specialization: Mapped[Optional[str]]  = mapped_column(String(128), nullable=True)
    assessment_date: Mapped[Optional[str]] = mapped_column(String(32),  nullable=True)

    # Job lifecycle
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    queued_at:   Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:  Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    report: Mapped[Optional["AssessmentReport"]] = relationship(
        "AssessmentReport", back_populates="job", uselist=False, lazy="select"
    )

    # Composite index for dashboard queries (patient + status)
    __table_args__ = (
        Index("ix_jobs_patient_status", "patient_id", "status"),
        Index("ix_jobs_finished_at",    "finished_at"),
    )

    def __repr__(self) -> str:
        return f"<AssessmentJob id={self.id} status={self.status}>"


# ---------------------------------------------------------------------------
# AssessmentReport
# Stores the complete final report as JSONB.
# 1-to-1 with AssessmentJob; only written once job is DONE.
#
# JSONB chosen over JSON for:
#   - Server-side filtering (e.g. WHERE report->'summary'->>'favorable' != '[]')
#   - GIN index support for future full-report search
#   - Efficient storage and comparison
# ---------------------------------------------------------------------------

class AssessmentReport(Base):
    __tablename__ = "assessment_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("assessment_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Full report blob — everything the worker produces
    report_json: Mapped[Any] = mapped_column(JSONB, nullable=False)

    # Denormalised summary counts for fast dashboard queries without JSON parsing
    total_medications: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    favorable_count:   Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    conditional_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unfavourable_count:Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overridden_count:  Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    job: Mapped["AssessmentJob"] = relationship(
        "AssessmentJob", back_populates="report"
    )

    # GIN index for JSONB search (e.g. contains queries)
    __table_args__ = (
        Index("ix_report_json_gin", "report_json", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<AssessmentReport job_id={self.job_id}>"
