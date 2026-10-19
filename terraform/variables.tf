variable "project_name" {
  description = "Short name used for Azure resource naming"
  type        = string
  default     = "entcopilot"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "francecentral"
}

variable "node_count" {
  description = "AKS default node pool size"
  type        = number
  default     = 1
}

variable "vm_size" {
  description = "AKS node VM size (must be allowed in the target region/subscription)"
  type        = string
  default     = "Standard_D2as_v7"
}

variable "kubernetes_version" {
  description = "AKS Kubernetes version (null = latest supported)"
  type        = string
  default     = null
}

variable "argocd_enabled" {
  description = "Install Argo CD via Helm"
  type        = bool
  default     = true
}

variable "argocd_chart_version" {
  description = "Argo CD Helm chart version"
  type        = string
  default     = "7.8.13"
}

variable "gitops_repo_url" {
  description = "Git repo URL watched by Argo CD"
  type        = string
  default     = ""
}

variable "gitops_target_revision" {
  description = "Git branch/tag for Argo CD"
  type        = string
  default     = "main"
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default = {
    project = "enterprise-copilot"
    managed = "terraform"
  }
}
