# HelixQA Phase 1.5 — Ingestion Services Implementation Guide

## Overview

Phase 1.5 adds **data ingestion pipelines** for test results, security findings, and performance metrics. This enables the quality score engine and AI agents to have the raw data they need to make recommendations.

**Completion Status:** ~30-40% of MVP feature set  
**Expected Duration:** 2 weeks  
**Dependencies:** Phase 1 backend (completed)

---

## What's New in Phase 1.5

### 1. Test Report Ingestion
**File:** `app/services/ingestion/test_ingestion.py`

Parses test reports from:
- **Jest** (JavaScript) — JSON format
- **Vitest** (JavaScript) — Jest-compatible
- **Mocha** (JavaScript) — JUnit XML output
- **Pytest** (Python) — JSON format
- **Unittest** (Python) — JUnit XML
- **JUnit** (Java) — XML format
- **Playwright** (E2E) — JSON format

**Features:**
- ✅ Framework-specific parsers (normalized to common model)
- ✅ Failure deduplication via fingerprinting (SHA256 hash of test_name + error)
- ✅ Coverage percent extraction
- ✅ Duration tracking

**API Endpoint:**
```
POST /api/v1/builds/{build_id}/ingest/tests
Content-Type: application/json

{
  "framework": "pytest",
  "report": { ...raw test report... }
}
```

### 2. Security Scan Ingestion
**File:** `app/services/ingestion/security_ingestion.py`

Parses security reports from:
- **Semgrep** (SAST) — JSON format
- **Trivy** (dependency/container scanning) — JSON format
- **OWASP ZAP** (dynamic analysis) — JSON format

**Features:**
- ✅ Severity classification (CRITICAL, HIGH, MEDIUM, LOW)
- ✅ Finding deduplication (rule_id + file + line)
- ✅ Risk score calculation (weighted by severity)
- ✅ CWE mapping (where applicable)

**API Endpoint:**
```
POST /api/v1/builds/{build_id}/ingest/security
Content-Type: application/json

{
  "tool": "semgrep",
  "report": { ...raw security report... }
}
```

### 3. Performance Metrics Ingestion
**File:** `app/services/ingestion/performance_ingestion.py`

Parses performance reports from:
- **K6** (load testing) — JSON summary
- **Lighthouse** (web performance) — JSON format
- **Apache JMeter** (load testing) — JSON format

**Features:**
- ✅ Latency extraction (avg, p95, p99, max)
- ✅ Throughput calculation (requests/sec)
- ✅ Error rate computation
- ✅ Core Web Vitals (Lighthouse)

**API Endpoint:**
```
POST /api/v1/builds/{build_id}/ingest/performance
Content-Type: application/json

{
  "tool": "k6",
  "report": { ...raw performance report... }
}
```

### 4. GitHub Webhook Integration
**File:** `app/services/github_webhook.py`  
**Endpoint:** `POST /api/v1/repos/{repo_id}/webhook`

Processes GitHub events:
- **push** — Creates Build entry
- **pull_request** — Tracks PR metadata
- **workflow_run** — Completes workflow, provides logs URL

**Features:**
- ✅ HMAC-SHA256 signature verification
- ✅ Event parsing (push, PR, workflow_run)
- ✅ Automatic Build/PR creation

---

## API Endpoints (New in Phase 1.5)

### Test Ingestion

```bash
# Ingest test report
POST /api/v1/builds/{build_id}/ingest/tests
Authorization: Bearer {token}
Content-Type: application/json

{
  "framework": "pytest",
  "report": { ...test report JSON... }
}

Response 201:
{
  "status": "ingested",
  "build_id": "...",
  "framework": "pytest",
  "total_tests": 100,
  "passed": 85,
  "failed": 5,
  "skipped": 10,
  "unique_failures": 3
}
```

```bash
# Get test results for build
GET /api/v1/builds/{build_id}/tests
Authorization: Bearer {token}

Response 200:
{
  "id": "...",
  "build_id": "...",
  "framework": "pytest",
  "total_tests": 100,
  "passed": 85,
  "failed": 5,
  "skipped": 10,
  "coverage_percent": 78.5,
  "unique_failures": 3,
  "failures": {
    "abc123def456": {
      "test_name": "test_auth_login",
      "error_message": "AssertionError: Expected 200, got 401",
      "file_path": "tests/test_auth.py"
    }
  }
}
```

### Security Ingestion

```bash
# Ingest security scan
POST /api/v1/builds/{build_id}/ingest/security
Authorization: Bearer {token}
Content-Type: application/json

{
  "tool": "semgrep",
  "report": { ...semgrep JSON... }
}

Response 201:
{
  "status": "ingested",
  "build_id": "...",
  "tool": "semgrep",
  "critical_count": 0,
  "high_count": 2,
  "medium_count": 5,
  "low_count": 10,
  "risk_score": 35.2,
  "total_findings": 17
}
```

```bash
# Get all security scans for build
GET /api/v1/builds/{build_id}/security
Authorization: Bearer {token}

Response 200: [ {...}, {...} ]

# Get specific tool's scan
GET /api/v1/builds/{build_id}/security?tool=semgrep
Authorization: Bearer {token}

Response 200:
{
  "id": "...",
  "build_id": "...",
  "tool": "semgrep",
  "critical_count": 0,
  "high_count": 2,
  "medium_count": 5,
  "low_count": 10,
  "risk_score": 35.2,
  "findings": {
    "CRITICAL": [],
    "HIGH": [
      {
        "id": "abc123",
        "rule_id": "python.lang.best-practice",
        "severity": "high",
        "file": "src/app.py",
        "line": 42,
        "message": "..."
      }
    ],
    "MEDIUM": [...],
    "LOW": [...]
  }
}
```

### Performance Ingestion

```bash
# Ingest performance report
POST /api/v1/builds/{build_id}/ingest/performance
Authorization: Bearer {token}
Content-Type: application/json

{
  "tool": "k6",
  "report": { ...k6 JSON... }
}

Response 201:
{
  "status": "ingested",
  "build_id": "...",
  "tool": "k6",
  "avg_response_time_ms": 250.5,
  "p95_response_time_ms": 800.0,
  "throughput_rps": 333.33,
  "error_rate_percent": 1.2
}
```

```bash
# Get all performance reports for build
GET /api/v1/builds/{build_id}/performance
Authorization: Bearer {token}

Response 200: [ {...}, {...} ]

# Get specific tool's report
GET /api/v1/builds/{build_id}/performance?tool=k6
Authorization: Bearer {token}

Response 200:
{
  "id": "...",
  "build_id": "...",
  "tool": "k6",
  "avg_response_time_ms": 250.5,
  "p95_response_time_ms": 800.0,
  "throughput_rps": 333.33,
  "error_rate_percent": 1.2,
  "raw_metrics": {
    "duration_metrics": {...},
    "test_duration_seconds": 60
  }
}
```

### GitHub Webhook

```bash
# GitHub sends this automatically (configure in repo settings)
# Webhook URL: https://your-api.com/api/v1/repos/{repo_id}/webhook
# Events: push, pull_request, workflow_run
# Headers:
#   X-Hub-Signature-256: sha256=<hmac>
#   X-GitHub-Event: push | pull_request | workflow_run

# Validates signature, creates Build/PR, returns 202
Response 202:
{
  "status": "created|queued",
  "event_type": "push|pull_request|workflow_run",
  "build_id": "...",
  ...
}
```

---

## Usage Examples

### Example 1: Ingest Pytest Report

```bash
# 1. Run Pytest with JSON output
pytest tests/ --json-report --json-report-file=report.json

# 2. Get your build ID
BUILD_ID="12345678-1234-1234-1234-123456789abc"
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# 3. Ingest the report
curl -X POST http://localhost:8000/api/v1/builds/$BUILD_ID/ingest/tests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @report.json

# 4. Check results
curl -X GET http://localhost:8000/api/v1/builds/$BUILD_ID/tests \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Example 2: Ingest Semgrep Findings

```bash
# 1. Run Semgrep
semgrep --json --output results.json src/

# 2. Ingest findings
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
BUILD_ID="12345678-1234-1234-1234-123456789abc"

curl -X POST http://localhost:8000/api/v1/builds/$BUILD_ID/ingest/security \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "semgrep",
    "report": '$(cat results.json)'
  }'

# 3. Retrieve findings
curl -X GET http://localhost:8000/api/v1/builds/$BUILD_ID/security?tool=semgrep \
  -H "Authorization: Bearer $TOKEN" | jq '.findings | to_entries[] | select(.value | length > 0)'
```

### Example 3: Ingest K6 Load Test Results

```bash
# 1. Run K6 test
k6 run --out json=results.json test.js

# 2. Parse JSON summary (may need to extract summary portion)
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
BUILD_ID="12345678-1234-1234-1234-123456789abc"

curl -X POST http://localhost:8000/api/v1/builds/$BUILD_ID/ingest/performance \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "k6",
    "report": '$(cat results.json | jq '.summary')'
  }'

# 3. Check performance metrics
curl -X GET http://localhost:8000/api/v1/builds/$BUILD_ID/performance?tool=k6 \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Example 4: GitHub Webhook Setup

```bash
# 1. Get your repo ID (from /api/v1/repos)
REPO_ID="87654321-4321-4321-4321-cba987654321"

# 2. Configure GitHub repo webhook
# Go to repo Settings > Webhooks > Add webhook
# Payload URL: https://your-api.com/api/v1/repos/$REPO_ID/webhook
# Content type: application/json
# Events: Let me select individual events
#   - Pushes
#   - Pull requests
#   - Workflow runs
# Secret: GITHUB_WEBHOOK_SECRET (from your .env)
# Active: ✓

# 3. Test webhook (GitHub provides "Redeliver" option after first attempt)
# Or manually trigger:
git push origin main  # Triggers push event
git pull request ...   # Triggers pull_request event
```

---

## Testing Ingestion Services

### Unit Tests

```python
# tests/test_ingestion_test_reports.py
import pytest
from app.services.ingestion.test_ingestion import JestReportParser, PytestReportParser


def test_jest_parser_basic():
    parser = JestReportParser()
    raw_report = {
        "numPassedTests": 85,
        "numFailedTests": 5,
        "numPendingTests": 10,
        "testResults": []
    }
    result = parser.parse(raw_report)
    assert result["total_tests"] == 100
    assert result["passed"] == 85
    assert result["failed"] == 5


def test_pytest_parser_with_failures():
    parser = PytestReportParser()
    raw_report = {
        "summary": {"total": 10, "passed": 8, "failed": 2, "skipped": 0},
        "tests": [
            {
                "nodeid": "tests/test_auth.py::test_login",
                "outcome": "failed",
                "call": {"longrepr": "AssertionError: expected 200"},
                "location": ["tests/test_auth.py", 42]
            }
        ]
    }
    result = parser.parse(raw_report)
    assert result["total_tests"] == 10
    assert result["failed"] == 2
    assert len(result["failure_fingerprints"]) > 0
```

### Integration Tests

```python
# tests/test_ingestion_api.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_ingest_pytest_report(client: AsyncClient, sample_build, db: AsyncSession):
    response = await client.post(
        f"/api/v1/builds/{sample_build.id}/ingest/tests",
        json={
            "framework": "pytest",
            "report": {
                "summary": {"total": 100, "passed": 85, "failed": 5, "skipped": 10},
                "tests": []
            }
        },
        headers={"Authorization": f"Bearer {get_token()}"}
    )
    assert response.status_code == 201
    assert response.json()["passed"] == 85
    
    # Verify persisted
    from app.models.analysis import TestRun
    test_run = await db.scalar(select(TestRun).where(TestRun.build_id == sample_build.id))
    assert test_run.passed == 85


@pytest.mark.asyncio
async def test_ingest_semgrep_findings(client: AsyncClient, sample_build):
    response = await client.post(
        f"/api/v1/builds/{sample_build.id}/ingest/security",
        json={
            "tool": "semgrep",
            "report": {
                "results": [
                    {
                        "check_id": "python.lang.best-practice",
                        "path": "src/app.py",
                        "start": {"line": 42},
                        "severity": "ERROR",
                        "message": "Use f-string"
                    }
                ]
            }
        },
        headers={"Authorization": f"Bearer {get_token()}"}
    )
    assert response.status_code == 201
    assert response.json()["high_count"] >= 1
```

---

## Integration with Quality Score Engine

Once test/security/performance data is ingested, the quality score engine automatically uses it:

```python
# Simplified flow
build = get_build(build_id)
test_run = get_test_run(build.id)
security_scans = get_security_scans(build.id)
perf_reports = get_performance_reports(build.id)

breakdown = compute_score_breakdown(
    coverage_percent=test_run.coverage_percent,
    test_pass_rate=(test_run.passed / test_run.total_tests * 100),
    critical_findings=sum(scan.critical_count for scan in security_scans),
    high_findings=sum(scan.high_count for scan in security_scans),
    # ... etc
)

# Score is now available at /api/v1/builds/{id}/quality-score
```

---

## Integration with AI Agents

Agents automatically use ingested data in their context:

```python
# app/tasks/pipeline.py (simplified)
test_run = get_test_run(build.id)
security_scan = get_security_scan(build.id)

root_cause_ctx = {
    "failing_tests": test_run.failure_fingerprints,  # ← From ingestion
    "recent_commits": [build.commit_sha],
    "build_logs": build.raw_log
}

security_ctx = {
    "findings": security_scan.findings  # ← From ingestion
}

root_cause_output = await RootCauseAgent().run(root_cause_ctx)
security_output = await SecurityAgent().run(security_ctx)
```

---

## Deduplication & Fingerprinting

All parsers use fingerprinting to deduplicate failures/findings:

```python
# Example: Pytest failure fingerprint
def _fingerprint_failure(self, test_name: str, error_msg: str) -> str:
    import hashlib
    key = f"{test_name}:{error_msg}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

# Grouped output
failure_fingerprints = {
    "a1b2c3d4e5f6g7h8": {
        "test_name": "test_login",
        "error_message": "AssertionError: ...",
        "file_path": "tests/test_auth.py"
    },
    # Multiple test failures grouped under same fingerprint
    # Only unique (test_name, error_message) pairs create new fingerprints
}

# Benefits:
# - Easily find "57 failures from same root cause"
# - Feed to Root Cause Agent as "3 unique failure patterns"
# - Avoids noise in agent context
```

---

## Performance Considerations

### Ingestion Latency
- **Small reports** (< 1MB): < 100ms
- **Medium reports** (1-10MB): 100-500ms
- **Large reports** (> 10MB): 500ms-2s

### Parsing Strategies
- Jest/Pytest: Direct JSON parsing (fast)
- JUnit: XML-to-dict conversion (slower)
- Lighthouse: Large JSON (slowest)

### Optimization Tips
1. **Batch failures/findings** — Group by fingerprint *before* sending
2. **Compress reports** — Gzip payloads if > 5MB
3. **Async queuing** — Use Celery for heavy lifting if needed

---

## Error Handling

All parsers gracefully handle malformed/partial data:

```python
try:
    parser = get_test_parser("pytest")
    result = parser.parse(raw_report)
except ValueError as e:
    # Unknown framework
    return {"error": str(e), "status_code": 400}
except KeyError as e:
    # Missing required field
    return {"error": f"Malformed report: {str(e)}", "status_code": 400}
except Exception as e:
    # Unexpected error
    return {"error": "Parser error", "status_code": 500}
```

---

## Next Steps (Phase 2)

After Phase 1.5:
1. Build Next.js frontend dashboard
2. Create real-time WebSocket updates
3. Add CI/CD integration (GitHub Actions, Jenkins, GitLab CI)
4. Implement test generation service
5. Add compliance report generation

---

## Files Added in Phase 1.5

**Ingestion Services:**
- `app/services/ingestion/test_ingestion.py` (Jest, Pytest, JUnit, Playwright)
- `app/services/ingestion/security_ingestion.py` (Semgrep, Trivy, OWASP ZAP)
- `app/services/ingestion/performance_ingestion.py` (K6, Lighthouse, JMeter)

**API Routes:**
- `app/api/v1/tests.py` (test ingestion endpoints)
- `app/api/v1/security.py` (security ingestion endpoints)
- `app/api/v1/performance.py` (performance ingestion endpoints)

**GitHub Integration:**
- `app/services/github_webhook.py` (webhook handler + signature validation)

**Documentation:**
- `PHASE_1_5.md` (this file)

**Updated Files:**
- `app/main.py` (added route includes)
- `app/api/v1/repos.py` (added webhook processing)

---

## Support

Questions?
1. Check examples above
2. Review parser docstrings in `app/services/ingestion/`
3. Run tests: `pytest tests/test_ingestion*.py`
4. Check Swagger docs: `http://localhost:8000/api/docs`

---

**Phase 1.5 Status:** Ready for development  
**Estimated Completion:** 2 weeks
