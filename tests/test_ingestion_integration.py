"""Example integration tests for Phase 1.5 ingestion services.
Run with: pytest tests/test_ingestion_integration.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import TestRun, SecurityScan, PerformanceReport

class TestTestIngestion:
    @pytest.mark.asyncio
    async def test_ingest_pytest_report(
        self, client: AsyncClient, sample_build, sample_pytest_report
    ):
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/tests",
            json={"framework": "pytest", "report": sample_pytest_report},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["passed"] == 85
        assert data["failed"] == 5
        assert data["skipped"] == 10
        assert data["unique_failures"] == 1

    @pytest.mark.asyncio
    async def test_ingest_jest_report(
        self, client: AsyncClient, sample_build, jest_report_fixture
    ):
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/tests",
            json={"framework": "jest", "report": jest_report_fixture},
        )
        assert response.status_code == 201
        assert response.json()["coverage_percent"] == 78.5

    @pytest.mark.asyncio
    async def test_get_test_results(
        self, client: AsyncClient, sample_build_with_test_results
    ):
        build, test_run = sample_build_with_test_results
        response = await client.get(
            f"/api/v1/builds/{build.id}/tests",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_tests"] == 100
        assert data["coverage_percent"] == 78.5
        assert len(data["failures"]) == 2

    @pytest.mark.asyncio
    async def test_ingest_unknown_framework(
        self, client: AsyncClient, sample_build
    ):
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/tests",
            json={"framework": "unknown_framework", "report": {}},
        )
        assert response.status_code == 400

class TestSecurityIngestion:

    @pytest.mark.asyncio
    async def test_ingest_semgrep_findings(
        self, client: AsyncClient, sample_build, semgrep_report_fixture
    ):
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/security",
            json={"tool": "semgrep", "report": semgrep_report_fixture},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["high_count"] >= 1
        assert data["risk_score"] > 0

    @pytest.mark.asyncio
    async def test_ingest_trivy_vulnerabilities(
        self, client: AsyncClient, sample_build, trivy_report_fixture
    ):
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/security",
            json={"tool": "trivy", "report": trivy_report_fixture},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["critical_count"] >= 1
        assert data["high_count"] >= 1

    @pytest.mark.asyncio
    async def test_get_security_scans_all(
        self, client: AsyncClient, sample_build_with_security_scan
    ):
        build, _ = sample_build_with_security_scan
        response = await client.get(
            f"/api/v1/builds/{build.id}/security",
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_get_security_scan_by_tool(
        self, client: AsyncClient, sample_build_with_security_scan
    ):
        build, _ = sample_build_with_security_scan
        response = await client.get(
            f"/api/v1/builds/{build.id}/security?tool=semgrep",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tool"] == "semgrep"
        assert "findings" in data

    @pytest.mark.asyncio
    async def test_security_scan_deduplication(
        self, client: AsyncClient, sample_build
    ):

        report = {
            "results": [
                {
                    "check_id": "rule1",
                    "path": "src/app.py",
                    "start": {"line": 42},
                    "severity": "ERROR",
                    "message": "Issue found"
                }
            ] * 3
        }
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/security",
            json={"tool": "semgrep", "report": report},
        )
        assert response.status_code == 201

class TestPerformanceIngestion:

    @pytest.mark.asyncio
    async def test_ingest_k6_results(
        self, client: AsyncClient, sample_build, k6_report_fixture
    ):
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/performance",
            json={"tool": "k6", "report": k6_report_fixture},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["avg_response_time_ms"] == 250.5
        assert data["p95_response_time_ms"] == 800.0
        assert data["throughput_rps"] > 0
        assert data["error_rate_percent"] == 1.2

    @pytest.mark.asyncio
    async def test_ingest_lighthouse_report(
        self, client: AsyncClient, sample_build, lighthouse_report_fixture
    ):
        response = await client.post(
            f"/api/v1/builds/{sample_build.id}/ingest/performance",
            json={"tool": "lighthouse", "report": lighthouse_report_fixture},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tool"] == "lighthouse"
        assert data["avg_response_time_ms"] == 1200

    @pytest.mark.asyncio
    async def test_get_performance_reports_all(
        self, client: AsyncClient, sample_build_with_perf_metrics
    ):
        build, _ = sample_build_with_perf_metrics
        response = await client.get(
            f"/api/v1/builds/{build.id}/performance",
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_get_performance_by_tool(
        self, client: AsyncClient, sample_build_with_perf_metrics
    ):
        build, _ = sample_build_with_perf_metrics
        response = await client.get(
            f"/api/v1/builds/{build.id}/performance?tool=k6",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tool"] == "k6"
        assert data["throughput_rps"] > 0

class TestQualityScoreIntegration:

    @pytest.mark.asyncio
    async def test_quality_score_uses_test_data(
        self, client: AsyncClient, sample_build_with_test_results, db: AsyncSession
    ):
        from app.models.analysis import QualityScore

        build, test_run = sample_build_with_test_results

        from app.services.quality_score import compute_score_breakdown

        breakdown = compute_score_breakdown(
            coverage_percent=test_run.coverage_percent,
            test_pass_rate=(test_run.passed / test_run.total_tests * 100),
            critical_findings=0,
            high_findings=0,
            medium_findings=0,
            low_findings=0,
            p95_response_ms=500,
            error_rate_percent=1.0,
            maintainability_index=75,
            code_smells=0,
            recent_build_success_rate=100,
        )

        assert breakdown.testing_score > 0
        assert breakdown.final_score > 0

    @pytest.mark.asyncio
    async def test_quality_score_uses_security_data(
        self, client: AsyncClient, sample_build_with_security_scan, db: AsyncSession
    ):
        from app.services.quality_score import compute_score_breakdown

        build, scan = sample_build_with_security_scan

        breakdown = compute_score_breakdown(
            coverage_percent=100,
            test_pass_rate=100,
            critical_findings=scan.critical_count,
            high_findings=scan.high_count,
            medium_findings=scan.medium_count,
            low_findings=scan.low_count,
            p95_response_ms=500,
            error_rate_percent=1.0,
            maintainability_index=75,
            code_smells=0,
            recent_build_success_rate=100,
        )

        assert breakdown.security_score < 100
        assert breakdown.final_score < 100
