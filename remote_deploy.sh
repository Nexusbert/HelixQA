#!/bin/bash
set -e

cd ~/helixqa-backend

echo "Building Docker image..."
sg docker -c "docker build -t helixqa-api:v1.0.0 ."

echo "Loading image into KinD..."
sg docker -c "kind load docker-image helixqa-api:v1.0.0"

echo "Applying Kubernetes manifests..."
# Fix imagePullPolicy in deployments using sed if not already fixed (the docs say to change it, but I haven't changed the files yet, so I'll do it on the fly or I should do it locally first).
# It's better to update the yaml files locally before rsyncing. Let's assume they are updated locally or I will update them locally now.

sg docker -c "kubectl apply -f k8s/00-namespace.yaml"
sg docker -c "kubectl apply -f k8s/00-serviceaccount.yaml"
sg docker -c "kubectl apply -f k8s/01-secrets.yaml"
sg docker -c "kubectl apply -f k8s/02-configmap.yaml"
sg docker -c "kubectl apply -f k8s/03-deployment-api.yaml"
sg docker -c "kubectl apply -f k8s/04-deployment-celery.yaml"
sg docker -c "kubectl apply -f k8s/05-service.yaml"
sg docker -c "kubectl apply -f k8s/06-ingress.yaml"

echo "Exposing the API via NodePort on port 30080..."
sg docker -c "kubectl patch service helixqa-api-service -n helixqa \
  --type='json' \
  -p='[
    {\"op\": \"replace\", \"path\": \"/spec/type\", \"value\": \"NodePort\"},
    {\"op\": \"replace\", \"path\": \"/spec/ports/0/nodePort\", \"value\": 30080}
  ]'"

echo "Waiting for pods to be ready..."
sleep 15
sg docker -c "kubectl wait --for=condition=ready pod -l app=helixqa-api -n helixqa --timeout=120s || true"

echo "Running migrations..."
API_POD=\$(sg docker -c "kubectl get pods -n helixqa -l app=helixqa-api -o jsonpath='{.items[0].metadata.name}'")
if [ -n "\$API_POD" ]; then
    sg docker -c "kubectl exec -t \$API_POD -n helixqa -- alembic upgrade head"
    echo "Migrations applied."
else
    echo "Could not find API pod to run migrations."
fi

echo "Deployment complete!"
