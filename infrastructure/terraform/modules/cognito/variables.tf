variable "pool_name" {
  description = "Name of the Cognito User Pool"
  type        = string
  default     = "dealwise"
}

variable "callback_urls" {
  description = "List of allowed callback URLs for the app client"
  type        = list(string)
  default     = ["http://localhost:3000/callback"]
}

variable "logout_urls" {
  description = "List of allowed logout URLs for the app client"
  type        = list(string)
  default     = ["http://localhost:3000/logout"]
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}
