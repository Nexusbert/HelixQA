# HelixQA Backend — Production Deployment Guide

## Pre-Deployment Checklist

### Security
- [ ] Generate cryptographically random `SECRET_KEY` (min 64 chars)
  ```bash
  openssl rand -hex 32
  ```
- [ ] Set `DEBUG=false`
- [ ] Rotate all API keys (AI providers, GitHub OAuth, etc.)
- [ ] Enable HTTPS/TLS (terminate at load balancer)
- [ ] Configure CORS to exact frontend domain(s)
- [ ] Set strong database password
- [ ] Enable Redis authentication with strong password
- [ ] Run security baseline scan (e.g., Trivy)
  ```bash
  trivy image helixqa-api:latest
  ```

### Infrastructure
- [ ] Managed PostgreSQL instance (AWS RDS, Google Cloud SQL, Azure Database)
- [ ] Managed Redis instance (AWS ElastiCache, Google Memorystore, Azure Cache)
- [ ] Load balancer (ALB, Cloud Load Balancer, etc.)
- [ ] Kubernetes cluster ready (if using K8s) or managed container platform (ECS, Cloud Run)
- [ ] DNS configured
- [ ] CDN configured (optional, for static assets)

### Monitoring & Observability
- [ ] Logging aggregation configured (CloudWatch, DataDog, Splunk, etc.)
- [ ] Error tracking enabled (Sentry, DataDog APM, etc.)
- [ ] Metrics collection running (Prometheus, DataDog, etc.)
- [ ] Alerting rules defined
- [ ] Incident response runbook created

### Testing
- [ ] Full test suite passing locally
- [ ] Integration tests against staging DB
- [ ] Load testing conducted (k6, Apache JMeter)
- [ ] Failover/recovery tested

---

## Deployment Methods

### Option 1: Docker + Kubernetes (Recommended for Scale)

#### Step 1: Build & Push Image

```bash
# Build
docker build -t helixqa-api:v0.1.0 .

# Tag for registry
docker tag helixqa-api:v0.1.0 myregistry.azurecr.io/helixqa/api:v0.1.0

# Push
docker push myregistry.azurecr.io/helixqa/api:v0.1.0
```

#### Step 2: Deploy to Kubernetes

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: helixqa

---
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: helixqa-secrets
  namespace: helixqa
type: Opaque
stringData:
  database-url: "postgresql+asyncpg://helixqa:STRONG_PASSWORD@postgres-prod.c123.us-east-1.rds.amazonaws.com:5432/helixqa_prod"
  redis-url: "redis://default:STRONG_PASSWORD@redis-prod.xyz.cache.amazonaws.com:6379/0"
  secret-key: "CRYPTOGRAPHICALLY_RANDOM_64_CHARS"
  anthropic-api-key: "sk-ant-..."
  github-webhook-secret: "ghp_..."

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: helixqa-config
  namespace: helixqa
data:
  environment: production
  debug: "false"
  allowed-origins: "https://app.helixqa.com"

---
# k8s/deployment-api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: helixqa-api
  namespace: helixqa
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: helixqa-api
  template:
    metadata:
      labels:
        app: helixqa-api
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
    spec:
      serviceAccountName: helixqa
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: api
        image: myregistry.azurecr.io/helixqa/api:v0.1.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
          protocol: TCP
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: helixqa-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: helixqa-secrets
              key: redis-url
        - name: CELERY_BROKER_URL
          value: "redis://default:STRONG_PASSWORD@redis-prod.xyz.cache.amazonaws.com:6379/1"
        - name: CELERY_RESULT_BACKEND
          value: "redis://default:STRONG_PASSWORD@redis-prod.xyz.cache.amazonaws.com:6379/2"
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: helixqa-secrets
              key: secret-key
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: helixqa-secrets
              key: anthropic-api-key
        - name: ENVIRONMENT
          valueFrom:
            configMapKeyRef:
              name: helixqa-config
              key: environment
        - name: DEBUG
          valueFrom:
            configMapKeyRef:
              name: helixqa-config
              key: debug
        - name: ALLOWED_ORIGINS
          valueFrom:
            configMapKeyRef:
              name: helixqa-config
              key: allowed-origins
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /api/health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
        volumeMounts:
        - name: tmp
          mountPath: /tmp
      volumes:
      - name: tmp
        emptyDir: {}

---
# k8s/deployment-celery.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: helixqa-celery-worker
  namespace: helixqa
spec:
  replicas: 2
  selector:
    matchLabels:
      app: helixqa-celery-worker
  template:
    metadata:
      labels:
        app: helixqa-celery-worker
    spec:
      serviceAccountName: helixqa
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
      - name: worker
        image: myregistry.azurecr.io/helixqa/api:v0.1.0
        env:
        # ... same as API deployment ...
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        command:
          - celery
          - -A
          - app.tasks.celery_app
          - worker
          - --loglevel=info
          - --concurrency=4

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: helixqa-api-service
  namespace: helixqa
spec:
  type: ClusterIP
  selector:
    app: helixqa-api
  ports:
  - name: http
    port: 8000
    targetPort: http
    protocol: TCP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: helixqa-ingress
  namespace: helixqa
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.helixqa.com
    secretName: helixqa-tls
  rules:
  - host: api.helixqa.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: helixqa-api-service
            port:
              number: 8000
```

Apply to cluster:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment-api.yaml
kubectl apply -f k8s/deployment-celery.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Verify rollout
kubectl rollout status deployment/helixqa-api -n helixqa
```

### Option 2: Docker Compose (Single Host / Staging)

```bash
# Production .env
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<RANDOM_64_CHARS>
DATABASE_URL=postgresql+asyncpg://helixqa:PASSWORD@postgres-host:5432/helixqa_prod
REDIS_URL=redis://redis-host:6379/0
ANTHROPIC_API_KEY=sk-ant-...

# Run with production override
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Option 3: Managed Platforms (Quick Wins)

**Google Cloud Run** (stateless FastAPI only, not Celery workers):

```bash
gcloud run deploy helixqa-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars DATABASE_URL=postgresql+asyncpg://... \
  --set-env-vars REDIS_URL=redis://... \
  --set-env-vars SECRET_KEY=... \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 100
```

**Azure Container Instances** (similar pattern).

---

## Database Migration (Production)

### Before First Deployment

```bash
# Offline migration (generates SQL without connecting)
alembic upgrade head --sql > migrations.sql

# Review migrations.sql, then run against prod DB
psql -h prod-postgres.xyz -U helixqa < migrations.sql
```

### After Deployment

```bash
# In API pod/container, run migrations
kubectl exec -it deployment/helixqa-api -n helixqa -- \
  alembic upgrade head
```

### Rollback (Emergency)

```bash
# See current revision
kubectl exec -it deployment/helixqa-api -n helixqa -- \
  alembic current

# Roll back 1 migration
kubectl exec -it deployment/helixqa-api -n helixqa -- \
  alembic downgrade -1
```

---

## Environment Configuration (Production)

Create a `.env.production` file (never commit to repo):

```env
ENVIRONMENT=production
DEBUG=false
APP_NAME=HelixQA

# Security
SECRET_KEY=<GENERATE: openssl rand -hex 32>
ALLOWED_ORIGINS=https://app.helixqa.com,https://admin.helixqa.com

# Database (use managed service)
DATABASE_URL=postgresql+asyncpg://helixqa:STRONG_PASS@helixqa-db-prod.c123.us-east-1.rds.amazonaws.com:5432/helixqa_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Redis (use managed service)
REDIS_URL=redis://default:STRONG_PASS@helixqa-redis-prod.cache.amazonaws.com:6379/0
CELERY_BROKER_URL=redis://default:STRONG_PASS@helixqa-redis-prod.cache.amazonaws.com:6379/1
CELERY_RESULT_BACKEND=redis://default:STRONG_PASS@helixqa-redis-prod.cache.amazonaws.com:6379/2

# AI Providers
AI_DEFAULT_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-<REDACTED>
OPENAI_API_KEY=sk-<REDACTED>
GEMINI_API_KEY=<REDACTED>

# GitHub OAuth
GITHUB_CLIENT_ID=Ov23liXXXXXXXX
GITHUB_CLIENT_SECRET=<REDACTED>
GITHUB_WEBHOOK_SECRET=whsec_<REDACTED>

# Google OAuth
GOOGLE_CLIENT_ID=<REDACTED>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<REDACTED>

# Security Scanners
SEMGREP_APP_TOKEN=<REDACTED>

# Monitoring/Observability
SENTRY_DSN=https://<REDACTED>@sentry.io/123456
DATADOG_API_KEY=<REDACTED>
```

Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, GitHub Secrets) instead of .env files.

---

## Monitoring & Alerting Setup

### Prometheus Metrics

FastAPI exports Prometheus-compatible metrics on `/metrics` (requires `prometheus-client` in requirements.txt).

```yaml
# prometheus-config.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: helixqa-api
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Datadog Integration (Recommended for SaaS)

```bash
# Install Datadog agent
pip install datadog

# Instrument FastAPI
from datadog import initialize, api
from ddtrace import patch_all

patch_all()
```

### Key Metrics to Track

1. **API Performance**
   - `http_requests_total` (by endpoint, status)
   - `http_request_duration_seconds` (p50, p95, p99)
   - Error rate (5xx responses)

2. **Analysis Pipeline**
   - `celery_task_total` (by task type, status)
   - `celery_task_duration_seconds` (by agent)
   - Queue depth (pending tasks)

3. **Agent Quality**
   - `agent_confidence_score` (histogram)
   - `agent_grounding_check_failures` (hallucination counter)
   - `agent_execution_duration` (by agent type)

4. **Database**
   - Connection pool utilization
   - Query latency
   - Replication lag (if using replicas)

### Alerting Rules

```yaml
# Example alert: High error rate
- alert: HelixQAHighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High error rate on {{ $labels.instance }}"
    
# Example alert: Celery queue backed up
- alert: CeleryQueueBacklog
  expr: celery_queue_length > 1000
  for: 10m
  annotations:
    summary: "Celery queue has {{ $value }} pending tasks"
```

---

## Secrets Management

### AWS Secrets Manager

```bash
# Store secrets
aws secretsmanager create-secret --name helixqa/db/url \
  --secret-string "postgresql+asyncpg://..."

aws secretsmanager create-secret --name helixqa/api-key \
  --secret-string "sk-ant-..."

# Retrieve in app
import boto3
sm = boto3.client('secretsmanager')
db_url = sm.get_secret_value(SecretId='helixqa/db/url')['SecretString']
```

### HashiCorp Vault

```bash
# Login
vault login -method=kubernetes role=helixqa

# Read secrets
vault kv get secret/helixqa/database
```

### GitHub Secrets (CI/CD Only)

```yaml
# .github/workflows/deploy.yml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

---

## Scaling Strategies

### Horizontal Scaling (FastAPI)

Each API instance is stateless and independent:

```bash
# Scale to 5 replicas in Kubernetes
kubectl scale deployment helixqa-api --replicas=5 -n helixqa

# Auto-scale based on CPU/memory
kubectl autoscale deployment helixqa-api --min=3 --max=10 --cpu-percent=70 -n helixqa
```

### Celery Worker Scaling

Add more workers for higher analysis throughput:

```bash
# Increase replicas
kubectl scale deployment helixqa-celery-worker --replicas=5 -n helixqa

# Monitor queue depth; scale up if backing up
kubectl exec -it deployment/helixqa-celery-worker -n helixqa -- \
  celery -A app.tasks.celery_app inspect active_queues
```

### Database Scaling

- **Read replicas:** Add read-only PostgreSQL replicas for reporting/dashboards
- **Connection pooling:** Use PgBouncer or connection pooler managed service
- **Sharding:** If >100B rows, consider sharding by organization_id

### Redis Scaling

- **Cluster mode:** For higher throughput, enable Redis Cluster
- **Replication:** Enable master-slave for HA (automatic failover)

---

## Incident Response

### Service Down

1. Check pod status: `kubectl get pods -n helixqa`
2. Check logs: `kubectl logs deployment/helixqa-api -n helixqa`
3. Check DB connectivity: `psql -h prod-db-host -U helixqa -c "SELECT 1"`
4. Check Redis: `redis-cli -h prod-redis-host ping`
5. Rollback if recent deployment: `kubectl rollout undo deployment/helixqa-api -n helixqa`

### High Error Rate

1. Check Datadog/Sentry for error patterns
2. Check database query performance (`EXPLAIN ANALYZE`)
3. Check Celery worker load (`celery inspect active`)
4. Scale up if CPU/memory saturated

### Memory Leak

1. Profile with `memory_profiler`: `python -m memory_profiler app/main.py`
2. Check for unclosed DB sessions/connections
3. Check Redis memory usage (`INFO memory`)
4. Restart affected pods to clear

---

## Blue-Green Deployment (Zero-Downtime)

```bash
# Current ("blue") deployment
kubectl get deployments -n helixqa

# Create new ("green") deployment
kubectl apply -f k8s/deployment-api-v0.2.0.yaml

# Verify green is healthy
kubectl rollout status deployment/helixqa-api-v0.2.0 -n helixqa

# Switch traffic (update service selector)
kubectl patch service helixqa-api-service -n helixqa \
  --type='json' -p='[{"op": "replace", "path": "/spec/selector/app", "value":"helixqa-api-v0.2.0"}]'

# If issues, revert
kubectl patch service helixqa-api-service -n helixqa \
  --type='json' -p='[{"op": "replace", "path": "/spec/selector/app", "value":"helixqa-api"}]'

# Cleanup old deployment
kubectl delete deployment helixqa-api -n helixqa
```

---

## Runbooks

### Weekly Maintenance

```bash
# Check replication lag
psql -h prod-db -U helixqa -c "SELECT pg_last_xlog_receive_location();"

# Analyze slow queries
psql -h prod-db -U helixqa -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Vacuum/analyze
psql -h prod-db -U helixqa -c "VACUUM ANALYZE;"

# Check disk usage
du -sh /var/lib/postgresql/data/

# Rotate logs
logrotate -f /etc/logrotate.d/helixqa
```

### Monthly Review

1. Review error trends (Sentry, Datadog)
2. Review agent accuracy (are recommendations matching outcomes?)
3. Review cost optimization (API calls, storage, compute)
4. Run security scan & fix vulnerabilities
5. Update dependencies

---

## Cost Optimization

1. **Database:** Use appropriate instance size; add read replicas only as needed
2. **Redis:** Size cache appropriately (don't over-provision)
3. **API:** Right-size container requests/limits; use HPA
4. **Celery:** Terminate workers when queue is empty
5. **AI API:** Batch requests where possible; cache responses for repeated queries

---

## References

- Kubernetes best practices: https://kubernetes.io/docs/concepts/configuration/overview/
- 12-Factor app: https://12factor.net/
- Prometheus monitoring: https://prometheus.io/docs/introduction/overview/
