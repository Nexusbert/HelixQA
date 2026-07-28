import uuid
import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Float, Text, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Build

class TestFramework(str, enum.Enum):
    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JUNIT = "junit"
    PLAYWRIGHT = "playwright"

class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TestRun(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "test_runs"

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE")
    )
    framework: Mapped[TestFramework] = mapped_column(Enum(TestFramework))
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    coverage_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_report: Mapped[dict] = mapped_column(JSON, default=dict)
    failure_fingerprints: Mapped[dict] = mapped_column(JSON, default=dict)

    build: Mapped["Build"] = relationship(back_populates="test_runs")

class SecurityScan(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "security_scans"

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE")
    )
    tool: Mapped[str] = mapped_column(String(50))
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    high_count: Mapped[int] = mapped_column(Integer, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, default=0)
    low_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    findings: Mapped[dict] = mapped_column(JSON, default=dict)

    build: Mapped["Build"] = relationship(back_populates="security_scans")

class PerformanceReport(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "performance_reports"

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE")
    )
    tool: Mapped[str] = mapped_column(String(50))
    avg_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    throughput_rps: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_rate_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    build: Mapped["Build"] = relationship(back_populates="performance_reports")

class QualityScore(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "quality_scores"

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE"), unique=True
    )
    testing_score: Mapped[float] = mapped_column(Float, default=0)
    security_score: Mapped[float] = mapped_column(Float, default=0)
    performance_score: Mapped[float] = mapped_column(Float, default=0)
    code_quality_score: Mapped[float] = mapped_column(Float, default=0)
    build_stability_score: Mapped[float] = mapped_column(Float, default=0)
    final_score: Mapped[float] = mapped_column(Float, default=0)
    category: Mapped[str] = mapped_column(String(50))
    recommendation: Mapped[str] = mapped_column(String(50))

    build: Mapped["Build"] = relationship(back_populates="quality_score")

class AgentReport(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "agent_reports"

    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builds.id", ondelete="CASCADE")
    )
    agent_type: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

class Notification(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(default=False)
    channel: Mapped[str] = mapped_column(String(50), default="in_app")

class AuditLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(255))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
