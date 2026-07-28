import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import PerformanceReport
from app.models.org import User
from app.models.repository import Build
from app.services.ingestion.performance_ingestion import get_performance_parser

router = APIRouter(prefix="/builds", tags=["performance-ingestion"])


class PerformanceReportIngestRequest(BaseModel):
    """Ingest performance metrics report for a build."""
    tool: str  # k6, lighthouse, jmeter
    report: dict  # Raw performance report (JSON)


@router.post("/{build_id}/ingest/performance", status_code=status.HTTP_201_CREATED)
async def ingest_performance_report(
    build_id: uuid.UUID,
    payload: PerformanceReportIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Ingest performance metrics report for a build.
    
    Parses tool-specific format into normalized PerformanceReport model.
    Extracts key metrics: latency, throughput, error rate.
    
    Supports: k6, lighthouse, jmeter
    """
    # Verify build exists
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")

    # Parse report via tool-specific parser
    try:
        parser = get_performance_parser(payload.tool)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    normalized = parser.parse(payload.report)

    # Delete existing report for this tool (replace, not append)
    existing = await db.execute(
        select(PerformanceReport).where(
            PerformanceReport.build_id == build.id,
            PerformanceReport.tool == payload.tool,
        )
    )
    old_report = existing.scalar_one_or_none()
    if old_report:
        await db.delete(old_report)
        await db.flush()

    # Create new performance report
    perf_report = PerformanceReport(
        build_id=build.id,
        tool=normalized["tool"],
        avg_response_time_ms=normalized.get("avg_response_time_ms"),
        p95_response_time_ms=normalized.get("p95_response_time_ms"),
        throughput_rps=normalized.get("throughput_rps"),
        error_rate_percent=normalized.get("error_rate_percent"),
        raw_metrics=normalized.get("raw_metrics", {}),
    )
    db.add(perf_report)
    await db.commit()
    await db.refresh(perf_report)

    return {
        "status": "ingested",
        "build_id": str(build.id),
        "tool": perf_report.tool,
        "avg_response_time_ms": perf_report.avg_response_time_ms,
        "p95_response_time_ms": perf_report.p95_response_time_ms,
        "throughput_rps": perf_report.throughput_rps,
        "error_rate_percent": perf_report.error_rate_percent,
    }


@router.get("/{build_id}/performance")
async def get_performance_report(
    build_id: uuid.UUID,
    tool: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict | list:
    """
    Get performance metrics for a build.
    
    If tool is specified, return that specific report.
    Otherwise, return all performance reports for the build.
    """
    if tool:
        result = await db.execute(
            select(PerformanceReport).where(
                PerformanceReport.build_id == build_id,
                PerformanceReport.tool == tool,
            )
        )
        perf_report = result.scalar_one_or_none()
        if not perf_report:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No performance data for tool: {tool}")

        return {
            "id": str(perf_report.id),
            "build_id": str(perf_report.build_id),
            "tool": perf_report.tool,
            "avg_response_time_ms": perf_report.avg_response_time_ms,
            "p95_response_time_ms": perf_report.p95_response_time_ms,
            "throughput_rps": perf_report.throughput_rps,
            "error_rate_percent": perf_report.error_rate_percent,
            "raw_metrics": perf_report.raw_metrics,
            "created_at": perf_report.created_at,
        }
    else:
        result = await db.execute(
            select(PerformanceReport).where(PerformanceReport.build_id == build_id)
        )
        reports = result.scalars().all()
        return [
            {
                "id": str(report.id),
                "tool": report.tool,
                "avg_response_time_ms": report.avg_response_time_ms,
                "p95_response_time_ms": report.p95_response_time_ms,
                "throughput_rps": report.throughput_rps,
                "error_rate_percent": report.error_rate_percent,
                "created_at": report.created_at,
            }
            for report in reports
        ]
