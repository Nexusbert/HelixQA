import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import SecurityScan
from app.models.org import User
from app.models.repository import Build
from app.services.ingestion.security_ingestion import get_security_parser

router = APIRouter(prefix="/builds", tags=["security-ingestion"])


class SecurityScanIngestRequest(BaseModel):
    """Ingest security scan report for a build."""
    tool: str  # semgrep, trivy, owasp_zap
    report: dict  # Raw security report (JSON)


@router.post("/{build_id}/ingest/security", status_code=status.HTTP_201_CREATED)
async def ingest_security_scan(
    build_id: uuid.UUID,
    payload: SecurityScanIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Ingest security scan report for a build.
    
    Parses tool-specific format into normalized SecurityScan model.
    Categorizes findings by severity (CRITICAL, HIGH, MEDIUM, LOW).
    Computes risk score based on finding distribution.
    
    Supports: semgrep, trivy, owasp_zap
    """
    # Verify build exists
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")

    # Parse report via tool-specific parser
    try:
        parser = get_security_parser(payload.tool)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    normalized = parser.parse(payload.report)

    # Delete existing scan for this tool (replace, not append)
    existing = await db.execute(
        select(SecurityScan).where(
            SecurityScan.build_id == build.id,
            SecurityScan.tool == payload.tool,
        )
    )
    old_scan = existing.scalar_one_or_none()
    if old_scan:
        await db.delete(old_scan)
        await db.flush()

    # Create new security scan
    sec_scan = SecurityScan(
        build_id=build.id,
        tool=normalized["tool"],
        critical_count=normalized["critical_count"],
        high_count=normalized["high_count"],
        medium_count=normalized["medium_count"],
        low_count=normalized["low_count"],
        risk_score=normalized["risk_score"],
        findings=normalized["findings"],
    )
    db.add(sec_scan)
    await db.commit()
    await db.refresh(sec_scan)

    return {
        "status": "ingested",
        "build_id": str(build.id),
        "tool": sec_scan.tool,
        "critical_count": sec_scan.critical_count,
        "high_count": sec_scan.high_count,
        "medium_count": sec_scan.medium_count,
        "low_count": sec_scan.low_count,
        "risk_score": sec_scan.risk_score,
        "total_findings": (
            sec_scan.critical_count
            + sec_scan.high_count
            + sec_scan.medium_count
            + sec_scan.low_count
        ),
    }


@router.get("/{build_id}/security")
async def get_security_scan(
    build_id: uuid.UUID,
    tool: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict | list:
    """
    Get security scan results for a build.
    
    If tool is specified, return that specific scan.
    Otherwise, return all scans for the build.
    """
    if tool:
        result = await db.execute(
            select(SecurityScan).where(
                SecurityScan.build_id == build_id,
                SecurityScan.tool == tool,
            )
        )
        sec_scan = result.scalar_one_or_none()
        if not sec_scan:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No security scan for tool: {tool}")

        return {
            "id": str(sec_scan.id),
            "build_id": str(sec_scan.build_id),
            "tool": sec_scan.tool,
            "critical_count": sec_scan.critical_count,
            "high_count": sec_scan.high_count,
            "medium_count": sec_scan.medium_count,
            "low_count": sec_scan.low_count,
            "risk_score": sec_scan.risk_score,
            "findings": sec_scan.findings,
            "created_at": sec_scan.created_at,
        }
    else:
        result = await db.execute(select(SecurityScan).where(SecurityScan.build_id == build_id))
        scans = result.scalars().all()
        return [
            {
                "id": str(scan.id),
                "tool": scan.tool,
                "critical_count": scan.critical_count,
                "high_count": scan.high_count,
                "medium_count": scan.medium_count,
                "low_count": scan.low_count,
                "risk_score": scan.risk_score,
                "created_at": scan.created_at,
            }
            for scan in scans
        ]
