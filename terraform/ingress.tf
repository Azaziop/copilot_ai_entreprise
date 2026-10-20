resource "kubernetes_namespace" "ingress_nginx" {
  count = var.ingress_nginx_enabled ? 1 : 0

  metadata {
    name = "ingress-nginx"
  }

  depends_on = [azurerm_kubernetes_cluster.main]
}

resource "helm_release" "ingress_nginx" {
  count = var.ingress_nginx_enabled ? 1 : 0

  name       = "ingress-nginx"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  version    = var.ingress_nginx_chart_version
  namespace  = kubernetes_namespace.ingress_nginx[0].metadata[0].name

  set {
    name  = "controller.service.type"
    value = "LoadBalancer"
  }

  set {
    name  = "controller.allowSnippetAnnotations"
    value = "true"
  }

  depends_on = [
    azurerm_role_assignment.aks_acr_pull,
    kubernetes_namespace.ingress_nginx,
  ]
}
