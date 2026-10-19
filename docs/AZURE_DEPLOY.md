# Deploy Enterprise Copilot on Azure (AKS + ACR + Argo CD)

## Architecture

1. **Terraform** creates Resource Group, ACR, AKS, AcrPull role, and installs **Argo CD** (Helm).
2. **GitHub Actions** builds/pushes Docker images to ACR and bumps tags in `k8s/overlays/azure`.
3. **Argo CD** syncs `k8s/overlays/azure` into the `enterprise-copilot` namespace.

```text
GitHub push → Actions (build/push ACR + tag bump) → Argo CD → AKS
                 ↘ Terraform (infra) ↗
```

## Prerequisites

- Azure subscription
- GitHub repository (this project)
- Azure CLI + Terraform locally (optional for first bootstrap)

## 1. Azure AD app + GitHub OIDC

Create an App Registration and federated credential for GitHub Actions (issuer `https://token.actions.githubusercontent.com`, subject `repo:OWNER/REPO:ref:refs/heads/main` and optionally `repo:OWNER/REPO:environment:azure-prod`).

Grant the app roles:

- `Contributor` on the subscription or target RG
- `User Access Administrator` (or ability to assign `AcrPull`) if Terraform creates role assignments

### GitHub secrets (Environment **`azure-prod`**)

| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | App registration client ID |
| `AZURE_TENANT_ID` | Directory (tenant) ID |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID |

Put these on the **`azure-prod`** environment (Settings → Environments → azure-prod → Environment secrets), not only as repo variables.

### GitHub variables

| Variable | Description |
|----------|-------------|
| `GITOPS_REPO_URL` | e.g. `https://github.com/OWNER/copilot_ai.git` |
| `ACR_LOGIN_SERVER` | Set after first Terraform apply (e.g. `entcopilotacrxxxxxx.azurecr.io`) |
| `PUBLIC_API_URL` | Public backend URL for Next.js build (`http://<backend-lb-ip>`) |
| `TF_AUTO_APPLY` | `true` to auto-apply Terraform on push to `main` (optional) |

Create GitHub Environment **`azure-prod`** (used by apply / CI jobs).

## 2. Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit gitops_repo_url, location, node_count
az login
terraform init
terraform plan
terraform apply
```

Optional remote state: copy `backend.tf.example` → `backend.tf` after creating a storage account.

Outputs:

```bash
terraform output acr_login_server
terraform output aks_name
terraform output -raw kube_config_raw > kubeconfig
export KUBECONFIG=$PWD/kubeconfig
```

Connect kubectl:

```bash
az aks get-credentials -g rg-entcopilot -n aks-entcopilot --overwrite-existing
```

## 3. Secrets on AKS (never commit real keys)

```bash
kubectl create namespace enterprise-copilot --dry-run=client -o yaml | kubectl apply -f -
kubectl -n enterprise-copilot create secret generic rag-secrets \
  --from-literal=OPENROUTER_API_KEY='sk-...' \
  --from-literal=LANGCHAIN_API_KEY='...' \
  --dry-run=client -o yaml | kubectl apply -f -
```

## 4. Argo CD

If Terraform `argocd_enabled=true`, Argo CD is installed in namespace `argocd` (server Service type LoadBalancer).

```bash
kubectl -n argocd get svc
# get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

Apply the Argo CD Application **after** `terraform apply` (it cannot be planned before AKS exists):

```bash
az aks get-credentials -g rg-entcopilot -n aks-entcopilot --overwrite-existing
kubectl apply -f argocd/application.yaml
```

## 5. CI image pipeline

On push to `main` (or `workflow_dispatch`):

1. Builds `Dockerfile` + `frontend/Dockerfile`
2. Pushes to ACR
3. Updates `k8s/overlays/azure/kustomization.yaml` image tags
4. Commits — Argo CD auto-syncs

After the backend LoadBalancer gets a public IP:

```bash
kubectl -n enterprise-copilot get svc rag-backend-service
```

Set GitHub variable `PUBLIC_API_URL=http://<IP>` and rebuild frontend (re-run CI). Optionally patch `k8s/overlays/azure/patch-configmap.yaml`.

## 6. Minikube (local, unchanged)

```bash
kubectl apply -k k8s/overlays/minikube
```

## Cost notes

Default AKS uses `Standard_B2s` × 2. Stop / destroy when idle:

```bash
cd terraform && terraform destroy
```
