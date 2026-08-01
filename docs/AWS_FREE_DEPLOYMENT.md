# Deploying HelixQA on AWS Free Tier with KinD (Kubernetes in Docker)

This guide walks you through deploying the HelixQA backend on AWS **completely for free** using a KinD Kubernetes cluster running inside an AWS Free Tier EC2 instance.

## Why KinD on EC2?

A standard AWS Free Tier instance (`t2.micro` or `t3.micro`) has only **1 GB of RAM**. Heavy Kubernetes distributions (k3s, microk8s) will exhaust this quickly. **KinD** runs Kubernetes nodes as lightweight Docker containers, allowing a multi-node cluster to fit inside this tiny memory footprint.

**External services used (all free tier):**
- **Database**: [Neon DB](https://neon.tech) — Free PostgreSQL
- **Redis / Celery Broker**: [Upstash](https://upstash.com) — Free Redis

---

## Architecture Overview

```
                            [ Internet ]
                                 │ (HTTP/HTTPS)
                                 ▼
                    [ EC2 t2.micro / t3.micro ]
                    [ Ubuntu 24.04 LTS         ]
                                 │
                          ┌──────┴──────┐
                          │   Docker    │
                          │   Engine    │
                          └──────┬──────┘
                                 │
                    ┌────────────┴────────────┐
                    │    KinD Cluster          │
                    │                         │
                    │  ┌─────────────────┐    │
                    │  │  control-plane  │    │
                    │  └─────────────────┘    │
                    │  ┌────────┐ ┌────────┐  │
                    │  │worker-1│ │worker-2│  │
                    │  └───┬────┘ └───┬────┘  │
                    └──────┼──────────┼───────┘
                           │          │ (External connections)
                    ┌──────┴──┐  ┌────┴─────────┐
                    │ Neon DB │  │ Upstash Redis │
                    └─────────┘  └──────────────┘
```

---

## Part 1: AWS Console Setup

### 1.1 Launch a Free EC2 Instance

1. Go to the **EC2 Dashboard** in your AWS Console.
2. Click **Launch Instance**.
3. Name your instance (e.g., `helixqa-k8s-node`).
4. Select **Ubuntu 24.04 LTS** (or 22.04 LTS) as the Amazon Machine Image (AMI).
5. Choose **t2.micro** (or `t3.micro` if available) — marked as **"Free tier eligible"**.
6. Create or select a **Key pair** to SSH into the machine.
7. Under **Network Settings**:
   - Check **Allow SSH traffic from anywhere** (or restrict to your IP).
   - Check **Allow HTTP traffic from the internet**.
   - Check **Allow HTTPS traffic from the internet**.
8. Under **Configure Storage**, set root volume to **30 GB** gp3 (free tier allows up to 30 GB).
9. Click **Launch Instance**.

### 1.2 Connect to Your Instance

Once running, select the instance and click **Connect**, or SSH via your terminal:

```bash
ssh -i "your-key.pem" ubuntu@your-instance-public-ip
```

---

## Part 2: Server Setup (Run on EC2)

### Step 1: Update the System

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### Step 2: Install Docker

KinD relies entirely on Docker to run the Kubernetes cluster.

```bash
sudo apt-get install docker.io -y

sudo systemctl start docker
sudo systemctl enable docker

sudo usermod -aG docker ubuntu
```

> **⚠️ Important**: Log out of your EC2 instance (`exit`) and log back in for the group changes to take effect.

### Step 3: Install KinD

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64

chmod +x ./kind

sudo mv ./kind /usr/local/bin/kind
```

### Step 4: Install kubectl

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
```

### Step 5: Create the Kubernetes Cluster

Create a KinD configuration file with port mappings so the API is accessible from outside:

```bash
cat <<EOF > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30080
    hostPort: 80
    protocol: TCP
  - containerPort: 30443
    hostPort: 443
    protocol: TCP
EOF
```

Create the cluster:

```bash
kind create cluster --config kind-config.yaml
```

This takes roughly 2–3 minutes. Verify:

```bash
kubectl get nodes
```

You should see one node (`control-plane`) with status `Ready`.

---

## Part 3: Deploy HelixQA

### Step 1: Load the Docker Image into KinD

Since KinD runs inside Docker (not connected to a remote registry), you build and load images directly:

```bash
# Clone or copy the HelixQA backend code to the EC2 instance
git clone <your-repo-url> helixqa-backend
cd helixqa-backend

# Build the Docker image
docker build -t helixqa-api:v1.0.0 .

# Load it into the KinD cluster (no registry needed)
kind load docker-image helixqa-api:v1.0.0
```

### Step 2: Update Deployment Manifests

Update the `image` field in both deployment files to use the local image name:

**In `k8s/03-deployment-api.yaml`** — change the image to:
```yaml
image: helixqa-api:v1.0.0
imagePullPolicy: Never
```

**In `k8s/04-deployment-celery.yaml`** — change the image to:
```yaml
image: helixqa-api:v1.0.0
imagePullPolicy: Never
```

> `imagePullPolicy: Never` tells Kubernetes to use the locally loaded image instead of trying to pull from a remote registry.

### Step 3: Apply Kubernetes Manifests

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/00-serviceaccount.yaml
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-configmap.yaml
kubectl apply -f k8s/03-deployment-api.yaml
kubectl apply -f k8s/04-deployment-celery.yaml
kubectl apply -f k8s/05-service.yaml
```

### Step 4: Expose the API via NodePort

To make the API reachable from the internet through the EC2 instance's public IP, modify the service type to `NodePort`:

```bash
kubectl patch service helixqa-api-service -n helixqa \
  --type='json' \
  -p='[
    {"op": "replace", "path": "/spec/type", "value": "NodePort"},
    {"op": "replace", "path": "/spec/ports/0/nodePort", "value": 30080}
  ]'
```

### Step 5: Run Database Migrations

```bash
API_POD=$(kubectl get pods -n helixqa -l app=helixqa-api -o jsonpath="{.items[0].metadata.name}")

kubectl exec -it $API_POD -n helixqa -- alembic upgrade head
```

### Step 6: Verify

```bash
kubectl get pods -n helixqa
```

All pods should show `Running` status. Test the health endpoint:

```bash
curl http://localhost/api/health
```

From your local machine, test using the EC2 public IP:

```bash
curl http://your-ec2-public-ip/api/health
```

---

## Part 4: Post-Deployment

### Configure GitHub OAuth Callback

1. Go to [GitHub Developer Settings](https://github.com/settings/developers).
2. Edit your OAuth App.
3. Set the **Authorization callback URL** to:
   ```
   http://your-ec2-public-ip/api/v1/auth/github/callback
   ```

### Configure GitHub Webhooks

1. Go to your repository **Settings → Webhooks**.
2. Set the **Payload URL** to:
   ```
   http://your-ec2-public-ip/api/v1/repos/{repo_id}/webhook
   ```
3. Set **Content type** to `application/json`.
4. Set **Secret** to the value of `GITHUB_WEBHOOK_SECRET` from your `.env`.
5. Select events: **Pushes**, **Pull requests**, **Workflow runs**.

### API Endpoints After Deployment

| Service | URL |
|---------|-----|
| Health Check | `http://your-ec2-public-ip/api/health` |
| API Docs | `http://your-ec2-public-ip/api/docs` |
| Auth Register | `POST http://your-ec2-public-ip/api/v1/auth/register` |
| Auth Login | `POST http://your-ec2-public-ip/api/v1/auth/login` |
| GitHub OAuth | `GET http://your-ec2-public-ip/api/v1/auth/github/callback?code=...` |
| Webhook | `POST http://your-ec2-public-ip/api/v1/repos/{repo_id}/webhook` |

---

## Cleanup

Because this setup runs on a Free Tier EC2 instance, you can leave it running 24/7 for the first year without charges (as long as you stay under 750 hours/month across all EC2 instances).

To wipe the Kubernetes cluster and start fresh:

```bash
kind delete cluster
```

To terminate the EC2 instance entirely, use the AWS Console: **EC2 → Instances → Select → Instance State → Terminate**.

---

## Cost Summary

| Resource | Cost |
|----------|------|
| EC2 t2.micro (750 hrs/month) | **$0** (Free Tier) |
| EBS 30 GB gp3 storage | **$0** (Free Tier) |
| Neon DB PostgreSQL | **$0** (Free Tier) |
| Upstash Redis | **$0** (Free Tier) |
| **Total Monthly Cost** | **$0** |
