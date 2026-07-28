from __future__ import annotations

import uuid
import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, Enum, ForeignKey, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.org import Organization
    from app.models.analysis import TestRun, SecurityScan, PerformanceReport, QualityScore

class VCSProvider(str, enum.Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"

class BuildStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Repository(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repositories"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    provider: Mapped[VCSProvider] = mapped_column(Enum(VCSProvider), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    webhook_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    organization: Mapped["Organization"] = relationship(back_populates="repositories")
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    builds: Mapped[list["Build"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

class PullRequest(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "pull_requests"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE")
    )
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(255))
    source_branch: Mapped[str] = mapped_column(String(255))
    target_branch: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(50), default="open")
    head_commit_sha: Mapped[str | None] = mapped_column(String(64))

    repository: Mapped["Repository"] = relationship(back_populates="pull_requests")

class Build(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "builds"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE")
    )
    commit_sha: Mapped[str] = mapped_column(String(64))
    branch: Mapped[str] = mapped_column(String(255))
    ci_provider: Mapped[str] = mapped_column(String(50))
    external_build_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[BuildStatus] = mapped_column(Enum(BuildStatus), default=BuildStatus.QUEUED)
    logs_url: Mapped[str | None] = mapped_column(String(1000))
    raw_log: Mapped[str | None] = mapped_column(Text)

    repository: Mapped["Repository"] = relationship(back_populates="builds")
    test_runs: Mapped[list["TestRun"]] = relationship(
        back_populates="build", cascade="all, delete-orphan"
    )
    security_scans: Mapped[list["SecurityScan"]] = relationship(
        back_populates="build", cascade="all, delete-orphan"
    )
    performance_reports: Mapped[list["PerformanceReport"]] = relationship(
        back_populates="build", cascade="all, delete-orphan"
    )
    quality_score: Mapped["QualityScore"] = relationship(
        back_populates="build", uselist=False, cascade="all, delete-orphan"
    )
