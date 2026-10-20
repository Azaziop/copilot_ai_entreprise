locals {
  name_prefix = lower(replace(var.project_name, " ", ""))
  # ACR name: 5-50 alphanumerics
  acr_name = substr(replace("${local.name_prefix}acr${random_string.suffix.result}", "-", ""), 0, 50)
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_container_registry" "main" {
  name                = local.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_kubernetes_cluster" "main" {
  name                = "aks-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = "aks-${local.name_prefix}"
  kubernetes_version  = var.kubernetes_version

  default_node_pool {
    name       = "default"
    node_count = var.node_count
    vm_size    = var.vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  network_profile {
    network_plugin = "azure"
    network_policy = "azure"
  }

  tags = var.tags
}

# Allow AKS kubelet to pull from ACR
resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
}

resource "kubernetes_namespace" "argocd" {
  count = var.argocd_enabled ? 1 : 0

  metadata {
    name = "argocd"
  }

  depends_on = [azurerm_kubernetes_cluster.main]
}

resource "helm_release" "argocd" {
  count = var.argocd_enabled ? 1 : 0

  name       = "argo-cd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = var.argocd_chart_version
  namespace  = kubernetes_namespace.argocd[0].metadata[0].name

  set {
    name  = "configs.params.server\\.insecure"
    value = "true"
  }

  # ClusterIP: free public IP quota (subscription often capped at 3 in a region).
  # Access UI with: kubectl -n argocd port-forward svc/argo-cd-argocd-server 8080:443
  set {
    name  = "server.service.type"
    value = "ClusterIP"
  }

  depends_on = [
    azurerm_role_assignment.aks_acr_pull,
    kubernetes_namespace.argocd,
  ]
}

# Argo CD Application is applied AFTER the cluster exists (kubernetes_manifest
# cannot plan against a cluster that does not exist yet).
# See: kubectl apply -f ../argocd/application.yaml
