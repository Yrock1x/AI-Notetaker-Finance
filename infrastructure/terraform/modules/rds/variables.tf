variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.small"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Name of the database to create"
  type        = string
  default     = "dealwise"
}

variable "db_username" {
  description = "Master username for the database"
  type        = string
  default     = "dealwise_admin"
}

variable "vpc_id" {
  description = "VPC ID where the RDS instance will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the DB subnet group"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs to attach to the RDS instance"
  type        = list(string)
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}
