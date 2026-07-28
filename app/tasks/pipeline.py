"""
Full analysis pipeline for a single Build:
  1. Load test/security/performance/code-quality raw data (already ingested
     via webhook processors, not fetched here)
  2. Run deterministic quality score engine
  3. Run AI agents (test, security, performance, root cause) in parallel
  4. Run release readiness agent last, fed the outputs of step 2 + 3
  5. Persist AgentReport rows + QualityScore row
  6. Emit a Notification + WebSocket event

This is a synchronous Celery task; each async agent call is run via
asyncio.run since Celery workers are sync by default. For high throughput,
switch to a dedicated async worker pool (e.g. arq) in a later iteration.
"""
import asyncio
import uuid

from app.tasks.celery_app import celery_app


async def _run_pipeline_async(build_id: str) -> dict:
    from sqlalchemy import select

    from app.agents.root_cause_agent import RootCauseAgent
    from app.agents.security_agent import (
        PerformanceAgent,
        ReleaseReadinessAgent,
        SecurityAgent,
        TestAgent,
    )
    from app.db.session import AsyncSessionLocal
    from app.models.analysis import AgentReport, PerformanceReport, QualityScore, SecurityScan, TestRun
    from app.models.repository import Build
    from app.services.quality_score import compute_score_breakdown

    async with AsyncSessionLocal() as db:
        build = await db.get(Build, uuid.UUID(build_id))
        if not build:
            return {"error": "build_not_found"}

        test_run = (
            await db.execute(select(TestRun).where(TestRun.build_id == build.id))
        ).scalars().first()
        sec_scan = (
            await db.execute(select(SecurityScan).where(SecurityScan.build_id == build.id))
        ).scalars().first()
        perf_report = (
            await db.execute(select(PerformanceReport).where(PerformanceReport.build_id == build.id))
        ).scalars().first()

        # --- 1. Deterministic score (source of truth for the numeric score) ---
        breakdown = compute_score_breakdown(
            coverage_percent=test_run.coverage_percent if test_run else 0,
            test_pass_rate=(100 * test_run.passed / test_run.total_tests) if test_run and test_run.total_tests else 0,
            critical_findings=sec_scan.critical_count if sec_scan else 0,
            high_findings=sec_scan.high_count if sec_scan else 0,
            medium_findings=sec_scan.medium_count if sec_scan else 0,
            low_findings=sec_scan.low_count if sec_scan else 0,
            p95_response_ms=perf_report.p95_response_time_ms if perf_report else 0,
            error_rate_percent=perf_report.error_rate_percent if perf_report else 0,
            maintainability_index=70,  # TODO: wire from code quality engine (SonarQube/ESLint/Ruff ingestion)
            code_smells=0,
            recent_build_success_rate=100,  # TODO: compute from last N builds
        )

        quality_score = QualityScore(
            build_id=build.id,
            testing_score=breakdown.testing_score,
            security_score=breakdown.security_score,
            performance_score=breakdown.performance_score,
            code_quality_score=breakdown.code_quality_score,
            build_stability_score=breakdown.build_stability_score,
            final_score=breakdown.final_score,
            category=breakdown.category,
            recommendation="pending",
        )
        db.add(quality_score)

        # --- 2. AI agents (grounded explanations, not the score itself) ---
        root_cause_ctx = {
            "failing_tests": test_run.raw_report if test_run else {},
            "recent_commits": [build.commit_sha],
            "build_logs": (build.raw_log or "")[:4000],
        }
        security_ctx = {"findings": sec_scan.findings if sec_scan else {}}
        performance_ctx = {"metrics": perf_report.raw_metrics if perf_report else {}}

        root_cause_out, security_out, performance_out = await asyncio.gather(
            RootCauseAgent().run(root_cause_ctx),
            SecurityAgent().run(security_ctx),
            PerformanceAgent().run(performance_ctx),
        )

        readiness_out = await ReleaseReadinessAgent().run(
            {
                "quality_score": breakdown.__dict__ | {"final_score": breakdown.final_score},
                "security_report": security_out.to_dict(),
                "root_cause_report": root_cause_out.to_dict(),
            }
        )

        quality_score.recommendation = readiness_out.payload.get("recommendation", "deploy_with_caution")

        for agent_type, out in [
            ("root_cause", root_cause_out),
            ("security", security_out),
            ("performance", performance_out),
            ("release_readiness", readiness_out),
        ]:
            db.add(
                AgentReport(
                    build_id=build.id,
                    agent_type=agent_type,
                    summary=out.summary,
                    confidence=out.confidence,
                    payload=out.payload,
                )
            )

        await db.commit()
        return {"build_id": build_id, "final_score": breakdown.final_score, "recommendation": quality_score.recommendation}


@celery_app.task(name="pipeline.run_analysis_pipeline", bind=True, max_retries=2)
def run_analysis_pipeline(self, build_id: str) -> dict:
    return asyncio.run(_run_pipeline_async(build_id))
