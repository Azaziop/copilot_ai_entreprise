# Deploy Enterprise Copilot on Azure (AKS + ACR + Argo CD)

## Architecture

See **[FULL_AUTOMATION.md](./FULL_AUTOMATION.md)** for the end-to-end automated pipeline.

1. **Terraform** — RG, ACR, AKS, AcrPull, Argo CD, Ingress NGINX  
2. **GHA Platform** — secrets, Ingress, Argo Application  
3. **GHA CI** — build/push ACR, auto `PUBLIC_API_URL` from Ingress, GitOps tag bump  
4. **Argo CD** — sync `k8s/overlays/azure` → AKS  

```text
git push → Platform + Build/Push → Argo CD → AKS (Ingress :80)
        ↘ Terraform apply (remote state) ↗
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
| `OPENROUTER_API_KEY` | Synced to K8s `rag-secrets` by Platform workflow |
| `LANGCHAIN_API_KEY` | Synced to K8s `rag-secrets` by Platform workflow |

Put these on the **`azure-prod`** environment (Settings → Environments → azure-prod → Environment secrets).

### GitHub variables

| Variable | Description |
|----------|-------------|
| `GITOPS_REPO_URL` | e.g. `https://github.com/OWNER/copilot_ai.git` |
| `ACR_LOGIN_SERVER` | e.g. `entcopilotacrxxxxxx.azurecr.io` |
| `PUBLIC_API_URL` | Optional override; else CI uses `http://<INGRESS_IP>/api` |
| `TF_STATE_STORAGE_ACCOUNT` | Enable remote Terraform state + CI apply |
| `TF_AUTO_APPLY` | `true` to auto-apply Terraform on push to `main` |

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

**Remote state (required before CI Terraform):** copy `backend.tf.example` → `backend.tf` after creating a storage account, migrate local state, then re-enable the `push` trigger in `.github/workflows/terraform.yaml`. Until then, infra is managed locally (`terraform apply`); the GitHub Terraform workflow is `workflow_dispatch` / PR only so it does not fight an empty remote state.

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

## 3. Bootstrap with Ansible (namespace, secrets, Argo Application)

Preferred after `terraform apply` (replaces manual `kubectl` for secrets + Application). See [`ansible/README.md`](../ansible/README.md).

```powershell
az login
cd ansible
docker compose run --rm azure                                          # AKS/ACR + kubeconfig
docker compose run --rm -e PLAYBOOK=playbooks/bootstrap.yml ansible  # secrets + Argo app
docker compose run --rm -e PLAYBOOK=playbooks/status.yml ansible
```

See [`ansible/README.md`](../ansible/README.md). On Windows, Ansible runs via Docker (not natively).

Manual equivalent (if you skip Ansible):

```bash
kubectl create namespace enterprise-copilot --dry-run=client -o yaml | kubectl apply -f -
kubectl -n enterprise-copilot create secret generic rag-secrets \
  --from-literal=OPENROUTER_API_KEY='sk-...' \
  --from-literal=LANGCHAIN_API_KEY='...' \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f argocd/application.yaml
```

## 4. Argo CD

If Terraform `argocd_enabled=true`, Argo CD is installed in namespace `argocd`. The bootstrap playbook sets the server Service to **ClusterIP** (public IP quota).

```bash
# Argo CD UI
kubectl -n argocd port-forward svc/argo-cd-argocd-server 8080:443
# get admin password (user: admin)
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo
# open https://localhost:8080
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
