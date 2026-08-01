# HelixQA Kubernetes Deployment

## Files Created

All Kubernetes manifests are in `k8s/`:
- `00-namespace.yaml` & `00-serviceaccount.yaml` - Namespace and RBAC definition
- `01-secrets.yaml` - All sensitive configuration (DB, Redis, API keys)
- `02-configmap.yaml` - Non-sensitive configuration
- `03-deployment-api.yaml` - FastAPI deployment (3 replicas)
- `04-deployment-celery.yaml` - Celery worker deployment (2 replicas)
- `05-service.yaml` - ClusterIP service for API
- `06-ingress.yaml` - Ingress with TLS (Let's Encrypt)

For a step-by-step walk-through on deploying for free on AWS, see [AWS_FREE_DEPLOYMENT.md](../docs/AWS_FREE_DEPLOYMENT.md).

## Before You Deploy

### ✅ You Already Have

| Key | Status | Source |
|-----|--------|--------|
| `SECRET_KEY` | ✅ | .env |
| `DATABASE_URL` | ✅ | Neon DB |
| `REDIS_URL` | ✅ | Upstash |
| `CELERY_BROKER_URL` | ✅ | Upstash |
| `CELERY_RESULT_BACKEND` | ✅ | Upstash |
| `GEMINI_API_KEY` | ✅ | .env |
| `GITHUB_CLIENT_ID` | ✅ | .env |
| `GITHUB_CLIENT_SECRET` | ✅ | .env |
| `GITHUB_WEBHOOK_SECRET` | ✅ | .env |
| `SEMGREP_APP_TOKEN` | ✅ | .env |

### 🔴 You Need to Get / Configure

| Item | Purpose | Where to Get |
|------|---------|--------------|
| **Domain Name** | `api.yourdomain.com` | Namecheap, Cloudflare, etc. |
| **Kubernetes Cluster** | Host your services | EKS, GKE, AKS, or DigitalOcean |
| **Container Registry** | Push Docker images | Docker Hub, GitHub Container Registry, ECR |
| **cert-manager** | TLS certificates | Install in cluster: `kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml` |
| **Cluster Issuer** | Let's Encrypt | Create `cluster-issuer.yaml` for production |

### 📝 Files to Edit

1. **`k8s/configmap.yaml`** - Line 8:
   ```yaml
   allowed-origins: "https://app.yourdomain.com"  # ← YOUR FRONTEND
   ```

2. **`k8s/ingress.yaml`** - Lines 10, 18:
   ```yaml
   - hosts:
     - api.yourdomain.com  # ← YOUR API DOMAIN
     secretName: helixqa-tls
   - host: api.yourdomain.com  # ← SAME DOMAIN
   ```

3. **`k8s/deployment-api.yaml` + `k8s/deployment-celery.yaml`** - Line 15:
   ```yaml
   image: your-registry/helixqa-api:v1.0.0  # ← YOUR REGISTRY
   ```

4. **`.env`** - Line 34:
   ```env
   ALLOWED_ORIGINS=https://app.yourdomain.com  # ← YOUR FRONTEND
   ```

5. **`.env`** - Line 26:
   ```env
   GITHUB_OAUTH_CALLBACK_URL=https://api.yourdomain.com/api/auth/github/callback  # ← YOUR API DOMAIN
   ```

6. **GitHub OAuth App** - Register callback:
   - URL: `https://api.yourdomain.com/api/auth/github/callback`

## Deployment Steps

```bash
# 1. Build & push Docker image
 docker build -t your-registry/helixqa-api:v1.0.0 .
 docker push your-registry/helixqa-api:v1.0.0

# 2. Install cert-manager (if not installed)
 kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# 3. Create ClusterIssuer (for Let's Encrypt)
 kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# 4. Deploy HelixQA
 kubectl apply -f k8s/namespace.yaml
 kubectl apply -f k8s/secrets.yaml
 kubectl apply -f k8s/configmap.yaml
 kubectl apply -f k8s/deployment-api.yaml
 kubectl apply -f k8s/deployment-celery.yaml
 kubectl apply -f k8s/service.yaml
 kubectl apply -f k8s/ingress.yaml

# 5. Verify
 kubectl get pods -n helixqa
 kubectl rollout status deployment/helixqa-api -n helixqa
```

## Post-Deployment

1. **Configure DNS**: Point `api.yourdomain.com` to your cluster's load balancer IP
2. **Register GitHub OAuth Callback**: 
   - Go to: https://github.com/settings/applications
   - Edit your app → Callback URL: `https://api.yourdomain.com/api/auth/github/callback`
3. **Implement OAuth Callback**: The current `/api/auth/github/callback` endpoint is stubbed (returns 501)
4. **Test Webhook**: 
   ```bash
   curl -X POST https://api.yourdomain.com/api/repos/{repo-id}/webhook \
     -H "X-Hub-Signature-256: sha256=..." \
     -H "X-GitHub-Event: push" \
     -d '{"ref":"refs/heads/main"}'
   ```

## URLs After Deployment

| Service | URL |
|---------|-----|
| API | `https://api.yourdomain.com/api/...` |
| Docs | `https://api.yourdomain.com/api/docs` |
| Health | `https://api.yourdomain.com/api/health` |
| Webhook | `https://api.yourdomain.com/api/repos/{repo_id}/webhook` |
| OAuth Callback | `https://api.yourdomain.com/api/auth/github/callback` |
