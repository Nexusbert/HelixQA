# HelixQA

**AI-Powered Quality Assurance Platform**

HelixQA automatically evaluates your code quality by ingesting test results, security scans, and performance metrics from your CI/CD pipeline. It computes a deterministic quality score and provides AI-driven insights to help you decide: **Can I safely deploy this code?**

---

## Features

### Quality Scoring
- **Deterministic scoring** across 5 weighted categories
- **Testing Coverage** (30%): Test pass rates and coverage percentages
- **Security Health** (30%): Vulnerability severity and count analysis
- **Performance** (15%): Latency, throughput, and error rate metrics
- **Code Quality** (15%): Maintainability and code smell detection
- **Build Stability** (10%): Historical success rate tracking

### AI Agents
5 specialized AI agents provide actionable insights:
- **Test Agent**: Generate test cases, detect coverage gaps
- **Security Agent**: Explain vulnerabilities, prioritize risks, recommend fixes
- **Performance Agent**: Identify bottlenecks, suggest optimizations
- **Root Cause Agent**: Correlate failures, trace origins, group duplicates
- **Release Readiness Agent**: Final deploy/no-deploy recommendation

### Supported Integrations
- **Test Frameworks**: Jest, Pytest, JUnit, Vitest, Mocha, Unittest, Playwright
- **Security Tools**: Semgrep, Trivy, OWASP ZAP
- **Performance Tools**: K6, Lighthouse, JMeter
- **VCS Providers**: GitHub (webhooks), GitLab, Bitbucket
- **AI Providers**: Claude, OpenAI, Gemini (swap via `AI_DEFAULT_PROVIDER`)

---

## Quality Score Categories

| Score Range | Category | Recommendation |
|-------------|----------|----------------|
| 90-100 | Production Ready | Deploy |
| 75-89 | Minor Risks | Deploy with Caution |
| 50-74 | Needs Attention | Do Not Deploy |
| 0-49 | Block Release | Do Not Deploy |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose 2.0+
- Python 3.12+
- PostgreSQL 15+
- Redis 7+

### Local Development

1. **Clone and configure:**
   ```bash
   git clone <repository-url>
   cd helixqa/backend
   cp .env.example .env
   ```

2. **Set your environment variables** (in `.env`):
   ```bash
   export POSTGRES_USER=helixqa
   export POSTGRES_PASSWORD=your-secure-password
   export POSTGRES_DB=helixqa_db
   export SECRET_KEY=your-64-char-secret-key
   export ANTHROPIC_API_KEY=your-anthropic-key
   ```

3. **Start the stack:**
   ```bash
   docker-compose up -d
   ```

4. **Access the API:**
   - API: `http://localhost:8000`
   - Docs: `http://localhost:8000/api/docs`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HELIXQA PLATFORM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  GitHub/GitLab → Webhook → Build → Ingest → Score → AI → Decision    │
│              │          │          │          │          │          │
│              ▼          ▼          ▼          ▼          ▼          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    INGESTION LAYER                              │   │
│  │  Test Reports: Jest, Pytest, JUnit, Playwright, Vitest, Mocha   │   │
│  │  Security: Semgrep, Trivy, OWASP ZAP                            │   │
│  │  Performance: K6, Lighthouse, JMeter                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                        │
│                              ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  QUALITY SCORE ENGINE                           │   │
│  │  5 weighted categories → Single score (0-100)                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                        │
│                              ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     AI AGENTS                                   │   │
│  │  5 specialized agents generating insights                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                        │
│                              ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  DECISION                                       │   │
│  │  Deploy / Deploy with Caution / Do Not Deploy                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## API Usage

### Authentication

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com", "password":"secure_pass", "full_name":"John Doe"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com", "password":"secure_pass"}'

# Use the returned token in subsequent requests
TOKEN="your-access-token"
```

### Ingest Test Results

```bash
BUILD_ID="your-build-uuid"

curl -X POST http://localhost:8000/api/v1/builds/$BUILD_ID/ingest/tests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "framework": "pytest",
    "report": {
      "summary": {"total": 100, "passed": 85, "failed": 5, "skipped": 10},
      "tests": [...]
    }
  }'
```

### Ingest Security Findings

```bash
curl -X POST http://localhost:8000/api/v1/builds/$BUILD_ID/ingest/security \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "semgrep",
    "report": {
      "results": [
        {"check_id": "python.sql-injection", "path": "src/db.py", "severity": "ERROR"}
      ]
    }
  }'
```

### Ingest Performance Metrics

```bash
curl -X POST http://localhost:8000/api/v1/builds/$BUILD_ID/ingest/performance \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "k6",
    "report": {
      "metrics": {"http_req_duration": {"p95": 800}}
    }
  }'
```

### Get Quality Score

```bash
curl -X GET http://localhost:8000/api/v1/builds/$BUILD_ID/quality-score \
  -H "Authorization: Bearer $TOKEN"
```

### Get AI Agent Reports

```bash
curl -X GET http://localhost:8000/api/v1/builds/$BUILD_ID/agent-reports \
  -H "Authorization: Bearer $TOKEN"
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `REDIS_URL` | Yes | - | Redis connection string |
| `SECRET_KEY` | Yes | - | JWT signing key (64+ chars) |
| `AI_DEFAULT_PROVIDER` | Yes | claude | AI provider: claude, openai, gemini |
| `ANTHROPIC_API_KEY` | Yes | - | Required for Claude |
| `OPENAI_API_KEY` | Yes | - | Required for OpenAI |
| `GEMINI_API_KEY` | Yes | - | Required for Gemini |
| `ENVIRONMENT` | No | local | local, staging, production |
| `DEBUG` | No | false | Enable verbose logging |

---

## Project Structure

```
backend/
├── app/
│   ├── api/v1/               # REST API endpoints
│   │   ├── auth.py          # Authentication routes
│   │   ├── repos.py         # Repository management
│   │   ├── builds.py        # Build tracking
│   │   ├── tests.py         # Test ingestion
│   │   ├── security.py      # Security ingestion
│   │   └── performance.py   # Performance ingestion
│   ├── agents/              # AI agents
│   │   ├── base.py          # Base agent class
│   │   ├── test_agent.py    # Test analysis agent
│   │   ├── security_agent.py # Security analysis agent
│   │   ├── performance_agent.py # Performance analysis agent
│   │   ├── root_cause_agent.py # Root cause analysis agent
│   │   └── release_agent.py # Release readiness agent
│   ├── core/               # Core utilities
│   │   ├── config.py        # Settings management
│   │   ├── security.py      # JWT, password hashing
│   │   └── deps.py          # FastAPI dependencies
│   ├── db/                 # Database layer
│   │   └── session.py       # SQLAlchemy engine & session
│   ├── models/             # Data models
│   │   ├── mixins.py        # Base mixins
│   │   ├── org.py           # User, Organization, RBAC
│   │   ├── repository.py    # Repository, Build, PR
│   │   └── analysis.py      # TestRun, SecurityScan, QualityScore
│   ├── services/           # Business logic
│   │   ├── ingestion/       # Ingestion parsers
│   │   │   ├── test_ingestion.py
│   │   │   ├── security_ingestion.py
│   │   │   └── performance_ingestion.py
│   │   └── quality_score.py # Score computation
│   ├── tasks/              # Async tasks
│   │   ├── celery_app.py    # Celery configuration
│   │   └── pipeline.py      # Analysis pipeline
│   └── main.py              # FastAPI app entry
├── alembic/                 # Database migrations
├── docs/                   # Documentation
├── docker-compose.yml      # Local development stack
├── Dockerfile              # Container image
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## Deployment

### Docker

```bash
# Build the image
docker build -t helixqa-api:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes

See `docs/DEPLOYMENT.md` for Kubernetes deployment guides.

---

## Documentation

- [Quick Start](docs/QUICKSTART.md) - Get started in 5 minutes
- [Testing](docs/TESTING.md) - Running tests and development
- [Phase 1.5 Details](docs/PHASE_1_5.md) - Ingestion services implementation
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment

---

## Technology Stack

- **Backend**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL 15+ (async via SQLAlchemy 2.0)
- **Cache/Queue**: Redis 7+
- **Task Queue**: Celery
- **AI Providers**: Claude, OpenAI, Gemini
- **Containerization**: Docker
- **Orchestration**: Docker Compose, Kubernetes

---

## License

Proprietary SaaS. For issues or contributions, contact the HelixQA team.

---

## Support

For support, questions, or feedback:
- **Email**: support@helixqa.io
- **Documentation**: [HelixQA Docs](https://docs.helixqa.io)
- **Status**: [Status Page](https://status.helixqa.io)
