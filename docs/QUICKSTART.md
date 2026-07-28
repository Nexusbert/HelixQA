# HelixQA Backend — 5-Minute Quickstart

## Fastest Path to Running Locally

### Prerequisites
- Docker & Docker Compose installed
- Any AI provider key (Claude/OpenAI/Gemini) — optional but recommended

### 1. Clone & Setup (1 min)

```bash
cd backend
cp .env.example .env
```

Edit `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here  # or OPENAI_API_KEY, GEMINI_API_KEY
```

### 2. Spin Up Stack (2 min)

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (runs migrations automatically)
- Redis
- FastAPI on `http://localhost:8000`
- Celery worker (for async analysis)

### 3. Test It (2 min)

```bash
# Health check
curl http://localhost:8000/api/health

# Open interactive docs
open http://localhost:8000/api/docs

# Or register a user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "secure_pass_123",
    "full_name": "Test User"
  }'

# Login (save token)
RESPONSE=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"secure_pass_123"}')

TOKEN=$(echo $RESPONSE | jq -r '.access_token')
echo $TOKEN
```

### 4. Query the API

```bash
# List repos (empty for now)
curl -X GET "http://localhost:8000/api/v1/repos?organization_id=<org_id>" \
  -H "Authorization: Bearer $TOKEN"

# Check health
curl http://localhost:8000/api/health
```

---

## Next: Try the Full Flow

### Create an Organization & Link Repo

```bash
# In code, create an org (see README for details on multi-tenancy)
# For now, manually insert via DB:
docker-compose exec postgres psql -U helixqa -d helixqa_db -c \
  "INSERT INTO organizations (id, name, slug) VALUES (gen_random_uuid(), 'Test Org', 'test-org');"

ORG_ID="<id_from_above>"

# Link a GitHub repo (use a real repo you have access to)
curl -X POST http://localhost:8000/api/v1/repos \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "'$ORG_ID'",
    "provider": "github",
    "external_id": "123456789",
    "full_name": "myusername/myrepo",
    "default_branch": "main"
  }'

REPO_ID="<id_from_response>"
```

### Simulate a Build & Trigger Analysis

```bash
# Create a build
curl -X POST http://localhost:8000/api/v1/builds \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "'$REPO_ID'",
    "commit_sha": "abc123def456",
    "branch": "main",
    "ci_provider": "github_actions"
  }'

BUILD_ID="<id_from_response>"

# Ingest test results (manually insert via DB for MVP)
docker-compose exec postgres psql -U helixqa -d helixqa_db -c \
  "INSERT INTO test_runs (id, build_id, framework, total_tests, passed, failed, coverage_percent) 
   VALUES (gen_random_uuid(), '$BUILD_ID', 'pytest', 100, 85, 5, 78.5);"

# Ingest security scan
docker-compose exec postgres psql -U helixqa -d helixqa_db -c \
  "INSERT INTO security_scans (id, build_id, tool, critical_count, high_count, medium_count, low_count)
   VALUES (gen_random_uuid(), '$BUILD_ID', 'semgrep', 0, 2, 5, 10);"

# Trigger analysis (runs all agents + score engine)
curl -X POST http://localhost:8000/api/v1/builds/$BUILD_ID/analyze \
  -H "Authorization: Bearer $TOKEN"

# Check Celery worker logs
docker-compose logs -f celery-worker

# After ~10s, fetch quality score
curl -X GET http://localhost:8000/api/v1/builds/$BUILD_ID/quality-score \
  -H "Authorization: Bearer $TOKEN" | jq

# Fetch agent reports
curl -X GET http://localhost:8000/api/v1/builds/$BUILD_ID/agent-reports \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## Troubleshooting

### "Connection refused to postgres"
```bash
# Check if containers are running
docker-compose ps

# Restart
docker-compose down
docker-compose up -d
```

### "Agent returned malformed output"
- Check `docker-compose logs celery-worker`
- Verify AI provider key is valid
- Verify rate limits haven't been hit

### "Build analysis queue is backed up"
```bash
# Check Celery queue
docker-compose exec celery-worker celery -A app.tasks.celery_app inspect active

# Scale workers (in docker-compose.yml, increase `replicas` in celery-worker service)
```

### "Database migration failed"
```bash
# Check migration status
docker-compose exec api alembic current

# View migrations
docker-compose exec api alembic history

# Roll back
docker-compose exec api alembic downgrade -1

# Reapply
docker-compose exec api alembic upgrade head
```

---

## Stop & Cleanup

```bash
# Stop services
docker-compose down

# Stop + remove volumes (careful! deletes DB data)
docker-compose down -v
```

---

## What's Next?

1. **Read the full README.md** — architecture, API routes, deployment
2. **Read TESTING.md** — how to add tests
3. **Wire up GitHub integration** — webhook processing, PR tracking
4. **Build the Next.js frontend** — connects to this API on `/api/v1`
5. **Deploy to staging/prod** — see DEPLOYMENT.md

---

## Common Endpoints (Swagger Docs)

API docs auto-generated: http://localhost:8000/api/docs

**Core Routes:**
- `POST /api/v1/auth/register` — Create account
- `POST /api/v1/auth/login` — Get JWT token
- `GET /api/v1/auth/me` — Current user
- `GET /api/v1/repos` — List repositories
- `POST /api/v1/repos` — Link new repository
- `GET /api/v1/builds/{id}` — Get build details
- `POST /api/v1/builds/{id}/analyze` — Trigger analysis (async)
- `GET /api/v1/builds/{id}/quality-score` — Get computed score
- `GET /api/v1/builds/{id}/agent-reports` — Get AI insights

---

## Questions?

Check the README.md or DEPLOYMENT.md, or review the source code in `app/`.
