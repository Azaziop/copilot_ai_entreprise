output "resource_group_name" {
  description = "Azure resource group name"
  value       = azurerm_resource_group.main.name
}

output "location" {
  value = azurerm_resource_group.main.location
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "acr_login_server" {
  description = "ACR login server (use as image registry prefix)"
  value       = azurerm_container_registry.main.login_server
}

output "aks_name" {
  value = azurerm_kubernetes_cluster.main.name
}

output "aks_id" {
  value = azurerm_kubernetes_cluster.main.id
}

output "kube_config_raw" {
  description = "Kubeconfig for the AKS cluster"
  value       = azurerm_kubernetes_cluster.main.kube_config_raw
  sensitive   = true
}

output "argocd_namespace" {
  value = var.argocd_enabled ? "argocd" : null
}
