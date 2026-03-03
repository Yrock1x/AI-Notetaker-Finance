variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "create_provider" {
  description = "Whether to create the OIDC provider (set to false if it already exists in this account)"
  type        = bool
  default     = true
}

variable "github_org" {
  description = "GitHub organization or username"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}
