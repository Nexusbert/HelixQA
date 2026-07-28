"""Additional fixtures for Phase 1.5 ingestion testing."""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import TestRun, SecurityScan, PerformanceReport, TestFramework

@pytest.fixture
def jest_report_fixture() -> dict:
    return {
        "numPassedTests": 85,
        "numFailedTests": 5,
        "numPendingTests": 10,
        "coverage": {"lines": {"percentage": 78.5}},
        "testResults": [
            {
                "name": "tests/auth.test.js",
                "assertionResults": [
                    {
                        "title": "should login successfully",
                        "status": "passed",
                        "failureMessages": []
                    },
                    {
                        "title": "should handle invalid password",
                        "status": "failed",
                        "failureMessages": [
                            "AssertionError: Expected 401, got 500",
                            "at /tests/auth.test.js:42:15"
                        ]
                    }
                ]
            }
        ]
    }

@pytest.fixture
def sample_pytest_report() -> dict:
    return {
        "summary": {"total": 100, "passed": 85, "failed": 5, "skipped": 10},
        "tests": [
            {
                "nodeid": "tests/test_auth.py::test_login_success",
                "outcome": "passed",
                "call": {},
                "location": ["tests/test_auth.py", 10]
            },
            {
                "nodeid": "tests/test_auth.py::test_invalid_password",
                "outcome": "failed",
                "call": {"longrepr": "AssertionError: expected 401, got 500"},
                "location": ["tests/test_auth.py", 42]
            }
        ]
    }

@pytest.fixture
def playwright_report_fixture() -> dict:
    return {
        "stats": {
            "expected": 90,
            "unexpected": 5,
            "skipped": 5,
            "flaky": 0
        },
        "tests": [
            {
                "testId": "e2e-1",
                "title": "should navigate homepage",
                "file": "tests/e2e.spec.ts",
                "results": [
                    {"status": "passed", "error": None}
                ]
            },
            {
                "testId": "e2e-2",
                "title": "should login and dashboard loads",
                "file": "tests/e2e.spec.ts",
                "results": [
                    {
                        "status": "failed",
                        "error": {"message": "Timeout waiting for #dashboard"}
                    }
                ]
            }
        ]
    }

@pytest.fixture
def semgrep_report_fixture() -> dict:
    return {
        "results": [
            {
                "check_id": "python.lang.best-practice.use-fstring",
                "path": "src/app.py",
                "start": {"line": 42},
                "end": {"line": 42},
                "message": "Use f-string instead of .format()",
                "severity": "WARNING"
            },
            {
                "check_id": "python.flask.security.sql-injection",
                "path": "src/db.py",
                "start": {"line": 100},
                "end": {"line": 100},
                "message": "Potential SQL injection detected",
                "severity": "ERROR"
            },
            {
                "check_id": "python.secrets.hardcoded-secrets",
                "path": "src/config.py",
                "start": {"line": 5},
                "end": {"line": 5},
                "message": "Hardcoded password detected",
                "severity": "ERROR"
            }
        ]
    }

@pytest.fixture
def trivy_report_fixture() -> dict:
    return {
        "Results": [
            {
                "Target": "package.json",
                "Type": "npm",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2023-12345",
                        "Severity": "CRITICAL",
                        "Title": "Critical RCE in lodash",
                        "Description": "Remote code execution vulnerability in lodash",
                        "PkgName": "lodash",
                        "InstalledVersion": "4.17.19",
                        "FixedVersion": "4.17.21"
                    },
                    {
                        "VulnerabilityID": "CVE-2023-54321",
                        "Severity": "HIGH",
                        "Title": "XSS vulnerability in react",
                        "Description": "Cross-site scripting in React DOM",
                        "PkgName": "react",
                        "InstalledVersion": "16.13.1",
                        "FixedVersion": "17.0.0"
                    }
                ],
                "Misconfigurations": []
            }
        ]
    }

@pytest.fixture
def owasp_zap_report_fixture() -> dict:
    return {
        "site": [
            {
                "name": "http://localhost:8000",
                "alerts": [
                    {
                        "pluginid": "10038",
                        "alert": "X-Frame-Options Header Missing",
                        "riskcode": "2",
                        "confidence": "2",
                        "desc": "X-Frame-Options header not set",
                        "instances": [
                            {"url": "http://localhost:8000", "method": "GET"},
                            {"url": "http://localhost:8000/api", "method": "GET"}
                        ]
                    },
                    {
                        "pluginid": "10037",
                        "alert": "Server Leaks Version Information via HTTP Header",
                        "riskcode": "1",
                        "confidence": "2",
                        "desc": "Server header exposes version",
                        "instances": [
                            {"url": "http://localhost:8000", "method": "GET"}
                        ]
                    }
                ]
            }
        ]
    }

@pytest.fixture
def k6_report_fixture() -> dict:
    return {
        "root_group": {
            "name": "",
            "max_duration": 60000,
            "path": ""
        },
        "metrics": {
            "http_req_duration": {
                "type": "Trend",
                "values": {
                    "avg": 250.5,
                    "max": 1200,
                    "med": 200,
                    "min": 50,
                    "p(90)": 500,
                    "p(95)": 800,
                    "p(99)": 1100
                }
            },
            "http_reqs": {
                "type": "Counter",
                "values": {"count": 10000}
            },
            "http_req_failed": {
                "type": "Rate",
                "values": {"rate": 0.012}
            },
            "http_req_blocked": {
                "type": "Trend",
                "values": {"avg": 10}
            },
            "http_req_connecting": {
                "type": "Trend",
                "values": {"avg": 5}
            },
            "http_req_tls_handshaking": {
                "type": "Trend",
                "values": {"avg": 0}
            },
            "http_req_sending": {
                "type": "Trend",
                "values": {"avg": 1}
            },
            "http_req_waiting": {
                "type": "Trend",
                "values": {"avg": 230}
            },
            "http_req_receiving": {
                "type": "Trend",
                "values": {"avg": 4}
            }
        }
    }

@pytest.fixture
def lighthouse_report_fixture() -> dict:
    return {
        "lighthouseVersion": "9.6.0",
        "finalUrl": "https://example.com",
        "requestedUrl": "https://example.com",
        "audits": {
            "first-contentful-paint": {
                "score": 0.90,
                "numericValue": 1200,
                "displayValue": "1.2 s"
            },
            "speed-index": {
                "numericValue": 2000
            },
            "largest-contentful-paint": {
                "numericValue": 3000
            },
            "cumulative-layout-shift": {
                "numericValue": 0.1
            },
            "total-blocking-time": {
                "numericValue": 200
            }
        },
        "categories": {
            "performance": {"score": 0.90},
            "accessibility": {"score": 0.85},
            "best-practices": {"score": 0.92},
            "seo": {"score": 1.0}
        }
    }

@pytest.fixture
def jmeter_report_fixture() -> dict:
    return {
        "Total": {
            "totalCount": 10000,
            "failCount": 120,
            "successCount": 9880,
            "average": 250,
            "max": 1200,
            "min": 50,
            "percentiles": {
                "90.0": 500,
                "95.0": 800,
                "99.0": 1100
            }
        },
        "duration": 300000
    }

@pytest_asyncio.fixture
async def sample_build_with_test_results(db: AsyncSession, sample_build):
    test_run = TestRun(
        build_id=sample_build.id,
        framework=TestFramework.PYTEST,
        total_tests=100,
        passed=85,
        failed=5,
        skipped=10,
        coverage_percent=78.5,
        raw_report={"summary": {"total": 100}},
        failure_fingerprints={
            "abc123": {"test_name": "test_login", "error_message": "401 error"},
            "def456": {"test_name": "test_signup", "error_message": "timeout"},
        }
    )
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)
    return sample_build, test_run

@pytest_asyncio.fixture
async def sample_build_with_security_scan(db: AsyncSession, sample_build):
    from app.models.analysis import SecurityScan
    
    scan = SecurityScan(
        build_id=sample_build.id,
        tool="semgrep",
        critical_count=0,
        high_count=2,
        medium_count=5,
        low_count=10,
        risk_score=35.2,
        findings={
            "CRITICAL": [],
            "HIGH": [
                {
                    "id": "abc123",
                    "rule_id": "python.sql-injection",
                    "severity": "high",
                    "file": "src/db.py",
                    "line": 100
                }
            ],
            "MEDIUM": [],
            "LOW": []
        }
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return sample_build, scan

@pytest_asyncio.fixture
async def sample_build_with_perf_metrics(db: AsyncSession, sample_build):
    perf = PerformanceReport(
        build_id=sample_build.id,
        tool="k6",
        avg_response_time_ms=250.5,
        p95_response_time_ms=800.0,
        throughput_rps=333.33,
        error_rate_percent=1.2,
        raw_metrics={"test_duration_seconds": 60}
    )
    db.add(perf)
    await db.commit()
    await db.refresh(perf)
    return sample_build, perf
