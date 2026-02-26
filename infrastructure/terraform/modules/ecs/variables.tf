variable "cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
  default     = "dealwise"
}

variable "api_image" {
  description = "Docker image for the API service"
  type        = string
}

variable "worker_image" {
  description = "Docker image for the Celery worker service"
  type        = string
}

variable "cpu" {
  description = "CPU units for each task (1 vCPU = 1024)"
  type        = number
  default     = 256
}

variable "memory" {
  description = "Memory in MiB for each task"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Desired number of running tasks per service"
  type        = number
  default     = 1
}

variable "vpc_id" {
  description = "VPC ID where the ECS cluster will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for the ALB"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Map of security group IDs (alb, app)"
  type        = map(string)
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket for file storage"
  type        = string
}
