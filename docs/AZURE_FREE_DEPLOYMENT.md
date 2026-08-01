# Deploying HelixQA on Azure Kubernetes Service (AKS) for Free

This guide walks you through deploying the HelixQA FastAPI application and Celery workers on Microsoft Azure for free (or within your $200 Azure Free Credits / Trial quota).

To achieve a completely cost-free deployment, we use **external free-tier services** for databases and messaging:
*   **Database**: [Neon DB](https://neon.tech) (Free tier PostgreSQL)
*   **Redis Queue & Broker**: [Upstash](https://upstash.com) (Free tier Redis)

By hosting database and queue workloads on external free tiers, the AKS cluster only runs the application containers (FastAPI & Celery), allowing it to fit easily on a single burstable VM node.

---

## Architecture Overview

```
                                      [ Internet ]
                                           │ (HTTPS)
                                           ▼
                                 [ NGINX Ingress Controller ]
                                           │ (Route via Host)
                                           ▼
                                [ helixqa-api-service ]
                                  │ (REST API Traffic)
                                  ▼
      ┌────────────────────────────────────────────────────────────────────────┐
      │ AKS Cluster Namespace: helixqa                                         │
      │                                                                        │
      │   ┌───────────────┐        ┌───────────────┐                           │
      │   │  helixqa-api  │        │ helixqa-worker│                           │
      │   │     (FastAPI) │        │      (Celery) │                           │
      │   └──────┬──┬─────┘        └──────┬──┬─────┘                           │
      └──────────┼──┼─────────────────────┼──┼─────────────────────────────────┘
                 │  │                     │  │ (External connections)
                 ▼  └─────────┐ ┌─────────┘  ▼
         ┌──────────────┐   ┌─▼─▼───────────┐
         │   Neon DB    │   │ Upstash Redis │
         │ (PostgreSQL) │   │    (Queue)    │
         └──────────────┘   └───────────────┘
```

---

## 1. Prerequisites & Azure Setup

### Install Tools
Ensure you have the following installed locally:
*   [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
*   [Docker](https://docs.docker.com/get-docker/)
*   [kubectl](https://kubernetes.io/docs/tasks/tools/)

### Log in to Azure
```bash
az login
```
If you have multiple subscriptions, select the active free-trial subscription:
```bash
az account set --subscription "Your-Subscription-Name-Or-ID"
```

---

## 2. Resource Group & ACR Provisioning

### Create a Resource Group
Create a resource group in a region supporting standard free-tier VMs (such as `eastus` or `westeurope`):
```bash
az group create --name HelixQAResourceGroup --location eastus
```

### Create Azure Container Registry (ACR)
Create a Basic SKU Container Registry. Basic is the lowest tier and costs less than $5/month, which easily fits within the $200 free credit:
```bash
az acr create --resource-group HelixQAResourceGroup --name helixqaacr --sku Basic
```

---

## 3. Azure Kubernetes Service (AKS) Provisioning

Create a single-node AKS cluster using the **Free Cluster Management SKU**. To minimize node costs and fit within free budgets, we utilize the **Standard_B2s** burstable VM (2 vCPU, 4GB RAM), which costs around $30/month:

```bash
az aks create \
  --resource-group HelixQAResourceGroup \
  --name HelixQACluster \
  --node-count 1 \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys \
  --tier free \
  --attach-acr helixqaacr
```

### Connect kubectl to AKS
```bash
az aks get-credentials --resource-group HelixQAResourceGroup --name HelixQACluster
```

Verify your node is online:
```bash
kubectl get nodes
```

---

## 4. Build and Push Container Images

### Log in to ACR
```bash
az acr login --name helixqaacr
```

### Build & Tag the Image
In the root directory of the backend workspace, build the API/worker image:
```bash
docker build -t helixqaacr.azurecr.io/helixqa-api:v1.0.0 .
```

### Push the Image
```bash
docker push helixqaacr.azurecr.io/helixqa-api:v1.0.0
```

---

## 5. Configure Secrets & Deploy Applications

### Configure Secrets
Modify `k8s/01-secrets.yaml` to ensure your external Neon and Upstash credentials, API keys, and configurations are set. Under `stringData`:
*   `database-url` points to your **Neon DB** PostgreSQL instance.
*   `redis-url` and other `celery-*` connection strings point to your **Upstash Redis** instances.

Also, modify `k8s/02-configmap.yaml` with your app domains.

### Deploy Namespace & Configuration
```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/00-serviceaccount.yaml
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-configmap.yaml
```

### Deploy API & Workers
1. Open `k8s/03-deployment-api.yaml` and set the container `image` field to:
   `helixqaacr.azurecr.io/helixqa-api:v1.0.0`
2. Open `k8s/04-deployment-celery.yaml` and set the container `image` field to:
   `helixqaacr.azurecr.io/helixqa-api:v1.0.0`
3. Apply the workloads:
   ```bash
   kubectl apply -f k8s/03-deployment-api.yaml
   kubectl apply -f k8s/04-deployment-celery.yaml
   kubectl apply -f k8s/05-service.yaml
   ```

Verify all pods are running successfully:
```bash
kubectl get pods -n helixqa
```

---

## 6. Database Migrations

Once your application pods are online and connected to your external Postgres database, trigger the database migrations using the alembic CLI directly inside the running API pod:

```bash
# Get the API Pod name
API_POD=$(kubectl get pods -n helixqa -l app=helixqa-api -o jsonpath="{.items[0].metadata.name}")

# Exec into the container and trigger alembic upgrade
kubectl exec -it $API_POD -n helixqa -- alembic upgrade head
```

---

## 7. Ingress & TLS Setup

To route external HTTP traffic to your service for free and bind Let's Encrypt SSL certificates automatically:

### Step 1: Install NGINX Ingress Controller
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace helixqa \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/azure-load-balancer-resource-group"=HelixQAResourceGroup
```

Find your External IP address:
```bash
kubectl get services -n helixqa -w ingress-nginx-controller
```
Create a DNS A Record mapping `api.yourdomain.com` to this External IP.

### Step 2: Install cert-manager
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
```

### Step 3: Create ClusterIssuer
Create `cluster-issuer.yaml` for cert-manager:
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```
Apply it:
```bash
kubectl apply -f cluster-issuer.yaml
```

### Step 4: Apply Ingress Routes
```bash
kubectl apply -f k8s/06-ingress.yaml
```

Your API is now live, securely served over HTTPS at `https://api.yourdomain.com/api/v1/health`!
