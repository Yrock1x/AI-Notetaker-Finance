variable "bucket_name" {
  description = "Base name of the S3 bucket"
  type        = string
  default     = "dealwise-recordings"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}
