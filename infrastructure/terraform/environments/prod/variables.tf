###############################################################################
# Variables – Production Environment
###############################################################################

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.2.0.0/16"
}

# --- RDS --------------------------------------------------------------------

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 100
}

# --- ElastiCache ------------------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.r6g.large"
}

# --- ECS --------------------------------------------------------------------

variable "api_image" {
  description = "Docker image for the API service"
  type        = string
  default     = "dealwise/api:latest"
}

variable "worker_image" {
  description = "Docker image for the Celery worker service"
  type        = string
  default     = "dealwise/worker:latest"
}

variable "ecs_cpu" {
  description = "CPU units for ECS tasks"
  type        = number
  default     = 1024
}

variable "ecs_memory" {
  description = "Memory in MiB for ECS tasks"
  type        = number
  default     = 2048
}

variable "ecs_desired_count" {
  description = "Desired number of running tasks"
  type        = number
  default     = 3
}

# --- Cognito ----------------------------------------------------------------

variable "cognito_callback_urls" {
  description = "Cognito callback URLs"
  type        = list(string)
  default     = ["https://app.dealwise.ai/callback"]
}

variable "cognito_logout_urls" {
  description = "Cognito logout URLs"
  type        = list(string)
  default     = ["https://app.dealwise.ai/logout"]
}
