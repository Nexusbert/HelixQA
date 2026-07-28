import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import AgentReport, QualityScore
from app.models.org import User
from app.models.repository import Build
from app.schemas.common import AgentReportOut, BuildOut, QualityScoreOut

router = APIRouter(prefix="/builds", tags=["builds"])


@router.get("/{build_id}", response_model=BuildOut)
async def get_build(
    build_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Build:
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")
    return build


@router.get("/{build_id}/quality-score", response_model=QualityScoreOut)
async def get_quality_score(
    build_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityScore:
    result = await db.execute(select(QualityScore).where(QualityScore.build_id == build_id))
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quality score not yet computed for this build")
    return score


@router.get("/{build_id}/agent-reports", response_model=list[AgentReportOut])
async def get_agent_reports(
    build_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AgentReport]:
    result = await db.execute(select(AgentReport).where(AgentReport.build_id == build_id))
    return list(result.scalars().all())


@router.post("/{build_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(build_id: uuid.UUID) -> dict:
    """
    Enqueues the full agent pipeline (test/security/performance/root-cause,
    then release-readiness) as a Celery chain. See app/tasks/pipeline.py.
    """
    from app.tasks.pipeline import run_analysis_pipeline

    run_analysis_pipeline.delay(str(build_id))
    return {"status": "queued", "build_id": str(build_id)}
