variable "queue_name" {
  description = "Base name of the SQS queue"
  type        = string
  default     = "dealwise-tasks"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}
