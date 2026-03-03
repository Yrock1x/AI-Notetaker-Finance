###############################################################################
# DealWise AI – Dev Environment
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "dealwise-terraform-state"
    key            = "environments/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "dealwise-terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "dealwise"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

# --- Networking -------------------------------------------------------------

module "networking" {
  source = "../../modules/networking"

  vpc_cidr     = var.vpc_cidr
  environment  = "dev"
  project_name = "dealwise"
}

# --- ECR (Container Registry) ------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"

  environment = "dev"
}

# --- RDS (PostgreSQL + pgvector) -------------------------------------------

module "rds" {
  source = "../../modules/rds"

  instance_class     = var.rds_instance_class
  allocated_storage  = var.rds_allocated_storage
  db_name            = "dealwise"
  db_username        = "dealwise_admin"
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.security_group_ids["database"]]
  environment        = "dev"
}

# --- S3 (Recordings & Documents) ------------------------------------------

module "s3" {
  source = "../../modules/s3"

  bucket_name = "dealwise-recordings"
  environment = "dev"
}

# --- Cognito (Auth) --------------------------------------------------------

module "cognito" {
  source = "../../modules/cognito"

  pool_name     = "dealwise"
  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls
  environment   = "dev"
}

# --- ElastiCache (Redis) ---------------------------------------------------

module "elasticache" {
  source = "../../modules/elasticache"

  node_type          = var.redis_node_type
  num_cache_nodes    = 1
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.security_group_ids["cache"]]
  auth_token         = var.redis_auth_token
  environment        = "dev"
}

# --- Secrets (API Keys) ----------------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  environment = "dev"
}

# --- ECS (Fargate) ---------------------------------------------------------

module "ecs" {
  source = "../../modules/ecs"

  cluster_name       = "dealwise"
  api_image          = "${module.ecr.api_repository_url}:latest"
  worker_image       = "${module.ecr.worker_repository_url}:latest"
  cpu                = var.ecs_cpu
  memory             = var.ecs_memory
  desired_count      = var.ecs_desired_count
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids
  security_group_ids = module.networking.security_group_ids
  certificate_arn    = var.certificate_arn
  s3_bucket_arn      = module.s3.bucket_arn
  s3_bucket_name     = module.s3.bucket_name
  environment        = "dev"

  # Secrets Manager ARNs
  secret_arns = module.secrets.secret_arns

  # Cognito
  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_app_client_id = module.cognito.app_client_id
  cognito_domain        = module.cognito.domain

  # CORS – permissive for dev
  cors_origins = "*"
}

# --- SQS (Task Queues) ----------------------------------------------------

module "sqs" {
  source = "../../modules/sqs"

  queue_name  = "dealwise-tasks"
  environment = "dev"
}

# --- Monitoring (CloudWatch) -----------------------------------------------

module "monitoring" {
  source = "../../modules/monitoring"

  cluster_name = "dealwise"
  environment  = "dev"
}

# --- GitHub OIDC (CI/CD) ---------------------------------------------------

module "github_oidc" {
  source = "../../modules/github-oidc"

  environment     = "dev"
  create_provider = true
  github_org      = var.github_org
  github_repo     = var.github_repo
}

# --- Outputs ----------------------------------------------------------------

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
}

output "elasticache_endpoint" {
  description = "ElastiCache primary endpoint"
  value       = module.elasticache.endpoint
}

output "alb_dns_name" {
  description = "ALB DNS name (use for API access)"
  value       = module.ecs.alb_dns_name
}

output "ecr_api_url" {
  description = "ECR repository URL for API image"
  value       = module.ecr.api_repository_url
}

output "ecr_worker_url" {
  description = "ECR repository URL for worker image"
  value       = module.ecr.worker_repository_url
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "Cognito App Client ID"
  value       = module.cognito.app_client_id
}

output "github_deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions deployment"
  value       = module.github_oidc.deploy_role_arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "private_subnet_ids" {
  description = "Private subnet IDs (needed for CD pipeline)"
  value       = module.networking.private_subnet_ids
}

output "app_security_group_id" {
  description = "App security group ID (needed for CD pipeline)"
  value       = module.networking.security_group_ids["app"]
}
