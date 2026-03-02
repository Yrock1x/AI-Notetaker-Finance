###############################################################################
# Variables – Dev Environment
###############################################################################

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# --- RDS --------------------------------------------------------------------

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.small"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

# --- ElastiCache ------------------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
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
  default     = 256
}

variable "ecs_memory" {
  description = "Memory in MiB for ECS tasks"
  type        = number
  default     = 512
}

variable "ecs_desired_count" {
  description = "Desired number of running tasks"
  type        = number
  default     = 1
}

# --- Cognito ----------------------------------------------------------------

variable "cognito_callback_urls" {
  description = "Cognito callback URLs"
  type        = list(string)
  default     = ["http://localhost:3000/callback"]
}

variable "cognito_logout_urls" {
  description = "Cognito logout URLs"
  type        = list(string)
  default     = ["http://localhost:3000/logout"]
}
