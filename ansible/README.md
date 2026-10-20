# Ansible — Azure AKS bootstrap (post-Terraform)

Playbooks only (`playbooks/*.yml`).

| Playbook | Role |
|----------|------|
| `prepare_azure.yml` | `az account` / AKS / ACR checks + `az aks get-credentials` |
| `bootstrap.yml` | namespace, `rag-secrets` (from `.env`), Argo Application, ClusterIP |
| `status.yml` | Argo sync + pods/services |

Infra (RG, ACR, AKS, Argo Helm) stays in **Terraform**.

## Prerequisites

```powershell
az login
# once on the host — token is reused via ~/.azure mount
```

Repo-root `.env`: `OPENROUTER_API_KEY`, `LANGCHAIN_API_KEY`.

## Run (Docker — Windows)

From `ansible/`:

```powershell
# 1) Azure context + kubeconfig
docker compose run --rm azure

# 2) Bootstrap app on AKS
docker compose run --rm -e PLAYBOOK=playbooks/bootstrap.yml ansible

# 3) Status
docker compose run --rm -e PLAYBOOK=playbooks/status.yml ansible
```

## Run (native Linux / macOS)

```bash
az login
az aks get-credentials -g rg-entcopilot -n aks-entcopilot --overwrite-existing
# or: ansible-playbook playbooks/prepare_azure.yml

python -m pip install ansible kubernetes PyYAML
ansible-galaxy collection install -r requirements.yml -p .collections
ansible-playbook playbooks/bootstrap.yml
ansible-playbook playbooks/status.yml
```

Native Windows Python Ansible is unsupported (`OSError: get_blocking`).

## Variables

See `group_vars/all.yml`: `aks_resource_group`, `aks_name`, optional `acr_name`.
