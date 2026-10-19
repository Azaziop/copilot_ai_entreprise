# Kubernetes manifests

Use **Kustomize overlays** (do not apply root YAML directly).

## Minikube (local)

```bash
kubectl apply -k k8s/overlays/minikube
```

## Azure (Argo CD / AKS)

Path watched by Argo CD: `k8s/overlays/azure`.

Create secrets once:

```bash
kubectl create namespace enterprise-copilot --dry-run=client -o yaml | kubectl apply -f -
kubectl -n enterprise-copilot create secret generic rag-secrets \
  --from-literal=OPENROUTER_API_KEY='...' \
  --from-literal=LANGCHAIN_API_KEY='...'
```

Legacy files in this folder (`backend.yaml`, `frontend.yaml`, …) are kept for reference; prefer overlays.
