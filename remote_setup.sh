#!/bin/bash
set -e

echo "Updating system..."
sudo apt-get update
# sudo apt-get upgrade -y # Skip upgrade to save time

echo "Installing Docker..."
if ! command -v docker &> /dev/null; then
    sudo apt-get install docker.io -y
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ubuntu
fi

echo "Installing KinD..."
if ! command -v kind &> /dev/null; then
    curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64
    chmod +x ./kind
    sudo mv ./kind /usr/local/bin/kind
fi

echo "Installing kubectl..."
if ! command -v kubectl &> /dev/null; then
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x ./kubectl
    sudo mv ./kubectl /usr/local/bin/kubectl
fi

echo "Setting up KinD cluster..."
if ! kind get clusters | grep -q "kind"; then
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
    # Since we need docker permissions immediately, use sudo for kind or run as new group
    sg docker -c "kind create cluster --config kind-config.yaml"
fi
