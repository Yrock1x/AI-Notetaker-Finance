variable "cluster_name" {
  description = "Name of the ECS cluster for monitoring"
  type        = string
  default     = "dealwise"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}
