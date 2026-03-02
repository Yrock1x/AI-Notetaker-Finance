variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "num_cache_nodes" {
  description = "Number of cache nodes in the cluster"
  type        = number
  default     = 1
}

variable "vpc_id" {
  description = "VPC ID where the cache cluster will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the cache subnet group"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs to attach to the cache cluster"
  type        = list(string)
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "auth_token" {
  description = "Auth token (password) for Redis AUTH. Must be 16-128 chars. Required when transit encryption is enabled."
  type        = string
  sensitive   = true
}
