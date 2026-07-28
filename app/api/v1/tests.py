import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import TestRun
from app.models.org import User
from app.models.repository import Build
from app.schemas.common import UserOut
from app.services.ingestion.test_ingestion import get_test_parser

router = APIRouter(prefix="/builds", tags=["test-ingestion"])

class TestReportIngestRequest(BaseModel):
    framework: str
    report: dict


@router.post("/{build_id}/ingest/tests", status_code=status.HTTP_201_CREATED)
async def ingest_test_report(
    build_id: uuid.UUID,
    payload: TestReportIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")

    try:
        parser = get_test_parser(payload.framework)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    normalized = parser.parse(payload.report)

    existing = await db.execute(select(TestRun).where(TestRun.build_id == build.id))
    old_run = existing.scalar_one_or_none()
    if old_run:
        await db.delete(old_run)
        await db.flush()

    test_run = TestRun(
        build_id=build.id,
        framework=normalized["framework"],
        total_tests=normalized["total_tests"],
        passed=normalized["passed"],
        failed=normalized["failed"],
        skipped=normalized["skipped"],
        coverage_percent=normalized.get("coverage_percent"),
        raw_report=normalized["raw_report"],
        failure_fingerprints=normalized["failure_fingerprints"],
    )
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    return {
        "status": "ingested",
        "build_id": str(build.id),
        "framework": test_run.framework,
        "total_tests": test_run.total_tests,
        "passed": test_run.passed,
        "failed": test_run.failed,
        "skipped": test_run.skipped,
        "coverage_percent": test_run.coverage_percent,
        "unique_failures": len(test_run.failure_fingerprints),
    }

@router.get("/{build_id}/tests")
async def get_test_run(
    build_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(TestRun).where(TestRun.build_id == build_id))
    test_run = result.scalar_one_or_none()
    if not test_run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No test results for this build")

    return {
        "id": str(test_run.id),
        "build_id": str(test_run.build_id),
        "framework": test_run.framework,
        "total_tests": test_run.total_tests,
        "passed": test_run.passed,
        "failed": test_run.failed,
        "skipped": test_run.skipped,
        "coverage_percent": test_run.coverage_percent,
        "duration_seconds": test_run.duration_seconds,
        "unique_failures": len(test_run.failure_fingerprints),
        "failures": test_run.failure_fingerprints,
        "created_at": test_run.created_at,
    }
