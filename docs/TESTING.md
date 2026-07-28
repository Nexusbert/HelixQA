# HelixQA Backend Testing Strategy

## Testing Pyramid

```
         /\
        /  \
       / E2E \          (User workflows, CI/CD integration tests)
      /______\
     /        \
    /  Unit    \        (Agent logic, score engine, auth)
   /____________\
  /              \
 / Integration    \     (API routes, DB transactions, Celery tasks)
/__________________\
```

## Test Coverage Goals

- **Unit Tests:** 80%+ (core business logic, agents, score engine)
- **Integration Tests:** 70%+ (API routes, database, Celery pipeline)
- **E2E Tests:** Key user workflows (register → link repo → trigger analysis → fetch score)

---

## Unit Testing

### Scope
- Quality score computation logic
- Agent grounding validation
- Token encoding/decoding
- Password hashing

### Example: Quality Score Engine

```python
# test_quality_score.py
import pytest
from app.services.quality_score import (
    compute_score_breakdown,
    score_testing,
    score_security,
)


def test_score_testing_perfect():
    """100% coverage + 100% pass rate = 100 score"""
    assert score_testing(coverage_percent=100, pass_rate=100) == 100.0


def test_score_testing_partial():
    """50% coverage, 75% pass rate = (50 + 75) / 2 = 62.5"""
    assert score_testing(coverage_percent=50, pass_rate=75) == 62.5


def test_score_security_no_findings():
    """Zero vulnerabilities = 100 score"""
    assert score_security(critical=0, high=0, medium=0, low=0) == 100.0


def test_score_security_critical_blocks():
    """One critical = -25 points"""
    assert score_security(critical=1, high=0, medium=0, low=0) == 75.0


def test_compute_score_breakdown():
    """Full breakdown weighting"""
    breakdown = compute_score_breakdown(
        coverage_percent=80,
        test_pass_rate=90,
        critical_findings=0,
        high_findings=2,
        medium_findings=5,
        low_findings=10,
        p95_response_ms=300,
        error_rate_percent=1.0,
        maintainability_index=75,
        code_smells=3,
        recent_build_success_rate=95,
    )
    # 0.30 * 85 + 0.30 * 70 + 0.15 * 90 + 0.15 * 74.5 + 0.10 * 95
    assert 70 < breakdown.final_score < 85
    assert breakdown.category == "minor_risks"
```

### Example: Agent Grounding

```python
# test_agent_grounding.py
import pytest
from app.agents.base import BaseAgent


@pytest.mark.asyncio
async def test_agent_rejects_ungrounded():
    """Agent downgrades confidence if evidence not found in context"""
    agent = RootCauseAgent()
    context = {
        "failing_tests": ["test_login_fails"],
        "recent_commits": ["abc123"],
        "build_logs": "Login module regression"
    }
    output = await agent.run(context)
    # If payload references "xyz789" commit that doesn't exist in context,
    # confidence should be downgraded (see base.py _validate_grounding)
    assert output.confidence <= 0.4  # guarded/downgraded
```

---

## Integration Testing

### Scope
- FastAPI route handlers
- Database transactions (rollback on failure)
- Celery task execution
- Provider abstraction

### Setup: pytest + pytest-asyncio + pytest-postgresql

```bash
pip install pytest pytest-asyncio pytest-postgresql
```

### Example: Auth Routes

```python
# test_api_auth.py
import pytest
from httpx import AsyncClient
from app.main import app
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db: AsyncSession):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "secure123", "full_name": "Test User"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    
    # Verify persisted to DB
    from app.models.org import User
    user = await db.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db: AsyncSession):
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "pass123"}
    )
    # Second registration (same email)
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "pass456"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db: AsyncSession):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "pass123"}
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "pass123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
```

### Example: Build Analysis Pipeline

```python
# test_pipeline.py
import pytest
from unittest.mock import patch, AsyncMock
from app.tasks.pipeline import run_analysis_pipeline


@pytest.mark.asyncio
async def test_analysis_pipeline_full(db: AsyncSession, sample_build):
    """Full pipeline: score + 4 agents → reports persisted"""
    with patch("app.agents.root_cause_agent.RootCauseAgent.run") as mock_root:
        mock_root.return_value = AsyncMock(summary="Auth failure", confidence=0.95)
        
        result = await run_analysis_pipeline(str(sample_build.id))
        
        assert result["final_score"] > 0
        assert result["recommendation"] in ["deploy", "deploy_with_caution", "do_not_deploy"]
        
        # Verify AgentReport persisted
        from app.models.analysis import AgentReport
        reports = await db.scalars(select(AgentReport).where(AgentReport.build_id == sample_build.id))
        assert len(list(reports)) >= 3  # At least root_cause, security, performance
```

---

## Fixtures (conftest.py)

```python
# conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncSessionLocal as _AsyncSessionLocal

from app.db.session import Base, get_db
from app.main import app
from app.core.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db():
    """Create test database"""
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost/test_helixqa",
        echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(test_db):
    """Fresh session for each test (rollback after)"""
    async with _AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db):
    """FastAPI test client with overridden DB dependency"""
    async def override_get_db():
        yield db
    
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def sample_user(db):
    """Create a test user"""
    from app.models.org import User
    from app.core.security import hash_password
    
    user = User(
        email="test@example.com",
        hashed_password=hash_password("password123")
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def sample_org(db, sample_user):
    """Create a test organization"""
    from app.models.org import Organization, OrganizationMember, OrgRole
    
    org = Organization(name="Test Org", slug="test-org")
    db.add(org)
    await db.flush()
    
    member = OrganizationMember(
        organization_id=org.id,
        user_id=sample_user.id,
        role=OrgRole.OWNER
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)
    return org


@pytest.fixture
async def sample_build(db, sample_org):
    """Create a test build with data"""
    from app.models.repository import Repository, Build
    from app.models.analysis import TestRun, SecurityScan, PerformanceReport
    from app.models.analysis import TestFramework
    
    repo = Repository(
        organization_id=sample_org.id,
        provider="github",
        external_id="123",
        full_name="test/repo"
    )
    db.add(repo)
    await db.flush()
    
    build = Build(
        repository_id=repo.id,
        commit_sha="abc123def456",
        branch="main",
        ci_provider="github_actions"
    )
    db.add(build)
    await db.flush()
    
    test_run = TestRun(
        build_id=build.id,
        framework=TestFramework.PYTEST,
        total_tests=100,
        passed=85,
        failed=5,
        skipped=10,
        coverage_percent=78.5
    )
    db.add(test_run)
    
    sec_scan = SecurityScan(
        build_id=build.id,
        tool="semgrep",
        critical_count=0,
        high_count=2,
        medium_count=5,
        low_count=10
    )
    db.add(sec_scan)
    
    perf_report = PerformanceReport(
        build_id=build.id,
        tool="k6",
        avg_response_time_ms=250,
        p95_response_time_ms=500,
        error_rate_percent=0.5
    )
    db.add(perf_report)
    await db.commit()
    await db.refresh(build)
    return build
```

---

## Running Tests

```bash
# All tests
pytest

# Specific test file
pytest test_quality_score.py

# Specific test function
pytest test_quality_score.py::test_score_testing_perfect

# With coverage
pytest --cov=app --cov-report=html

# Parallel execution
pytest -n auto

# Verbose
pytest -v
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_helixqa
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: Run tests
        run: pytest backend --cov=backend/app --cov-report=xml
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test_helixqa
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

---

## Hallucination Testing (Agents)

Specialized tests to catch LLM fabrication:

```python
# test_agent_hallucinations.py
@pytest.mark.asyncio
async def test_agent_rejects_fabricated_findings():
    """Agent should not invent vulnerabilities not in input"""
    agent = SecurityAgent()
    empty_findings = {"findings": {}}
    output = await agent.run(empty_findings)
    
    # If agent lists vulnerabilities that don't exist, grounding fails
    assert output.confidence <= 0.4 or len(output.payload.get("findings", [])) == 0


@pytest.mark.asyncio
async def test_agent_confidence_reflects_certainty():
    """High-signal context → higher confidence"""
    agent = RootCauseAgent()
    
    # Unambiguous context
    clear_context = {
        "failing_tests": ["test_auth_login"],
        "recent_commits": ["abc123"],  # Same commit that changed auth.py
        "build_logs": "ImportError: AuthMiddleware"
    }
    output_clear = await agent.run(clear_context)
    
    # Ambiguous context
    ambiguous_context = {
        "failing_tests": ["test_1", "test_2", ..., "test_57"],
        "recent_commits": ["abc123", "def456", ...],
        "build_logs": "[truncated logs]"
    }
    output_ambiguous = await agent.run(ambiguous_context)
    
    # Clear context should have higher confidence
    assert output_clear.confidence >= output_ambiguous.confidence
```

---

## Performance Testing (Celery Tasks)

```python
# test_pipeline_performance.py
@pytest.mark.asyncio
async def test_pipeline_latency(benchmark, sample_build):
    """Full pipeline should complete in <30s"""
    
    def run_pipeline():
        asyncio.run(run_analysis_pipeline(str(sample_build.id)))
    
    result = benchmark(run_pipeline)
    # Benchmark reports latency; CI can fail if >30s
```

---

## Continuous Monitoring

Post-deployment, track:
1. **Agent accuracy:** Do recommendations match actual deployment outcomes?
2. **Score calibration:** Are 0-49 builds actually bad? Are 90+ always good?
3. **False positives:** Security findings that don't pan out?

Collect feedback and retrain/recalibrate quarterly.

---

## References

- Pytest: https://docs.pytest.org
- AsyncIO testing: https://docs.pytest.org/en/7.2.x/asyncio.html
- SQLAlchemy testing: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#using-test-fixtures
