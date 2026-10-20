# Full automation — Enterprise Copilot on Azure

## What “all automated” means here

```text
git push main
    │
    ├─► Platform bootstrap (GHA)
    │     • az aks get-credentials (OIDC)
    │     • helm ingress-nginx (1 public IP)
    │     • Secret rag-secrets ← GitHub secrets
    │     • kubectl apply Argo Application
    │
    ├─► Build & push (GHA)
    │     • resolve http://<INGRESS_IP>/api
    │     • build/push backend + frontend → ACR
    │     • commit kustomize tags (+ configmap URL)
    │
    ├─► Argo CD
    │     • sync k8s/overlays/azure → AKS
    │
    └─► Terraform (optional auto-apply)
          • needs remote state vars + TF_AUTO_APPLY=true
          • RG / ACR / AKS / Argo / Ingress (IaC)
```

## Public URLs (after Ingress)

| URL | Target |
|-----|--------|
| `http://<INGRESS_IP>/` | Frontend |
| `http://<INGRESS_IP>/api/...` | Backend (rewritten to `/...`) |

Argo CD UI stays private: `kubectl -n argocd port-forward svc/argo-cd-argocd-server 8080:80`

## GitHub Environment `azure-prod`

### Secrets (required)

| Secret | Purpose |
|--------|---------|
| `AZURE_CLIENT_ID` | OIDC app |
| `AZURE_TENANT_ID` | Directory |
| `AZURE_SUBSCRIPTION_ID` | Subscription |
| `OPENROUTER_API_KEY` | Synced into `rag-secrets` |
| `LANGCHAIN_API_KEY` | Synced into `rag-secrets` |

### Variables

| Variable | Purpose |
|----------|---------|
| `ACR_LOGIN_SERVER` | e.g. `entcopilotacrffl9pp.azurecr.io` |
| `GITOPS_REPO_URL` | Git repo for Argo |
| `PUBLIC_API_URL` | Optional override; else auto from Ingress |
| `TF_STATE_STORAGE_ACCOUNT` | Enable remote Terraform state / apply |
| `TF_STATE_RESOURCE_GROUP` | default `rg-entcopilot-tfstate` |
| `TF_AUTO_APPLY` | `true` to apply Terraform on push |

## One-time setup (remote Terraform state)

```bash
az group create -n rg-entcopilot-tfstate -l francecentral
az storage account create -n entcopilottfstate -g rg-entcopilot-tfstate -l francecentral --sku Standard_LRS
az storage container create -n tfstate --account-name entcopilottfstate

# Migrate existing local state (on your PC):
cd terraform
# create backend.tf from backend.tf.example, then:
terraform init -migrate-state
```

Set GitHub variable `TF_STATE_STORAGE_ACCOUNT=entcopilottfstate` and `TF_AUTO_APPLY=true`.

## Day-2 developer flow

1. Change app code  
2. `git push origin main`  
3. Wait for **Platform bootstrap** (if needed) + **Build and push to ACR**  
4. Argo shows Synced / Healthy  
5. Open `http://<INGRESS_IP>/`

No manual `kubectl` / Ansible required for routine deploys.
