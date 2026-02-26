###############################################################################
# DealWise AI – Staging Environment
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
    key            = "environments/staging/terraform.tfstate"
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
      Environment = "staging"
      ManagedBy   = "terraform"
    }
  }
}

# --- Networking -------------------------------------------------------------

module "networking" {
  source = "../../modules/networking"

  vpc_cidr     = var.vpc_cidr
  environment  = "staging"
  project_name = "dealwise"
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
  environment        = "staging"
}

# --- S3 (Recordings & Documents) ------------------------------------------

module "s3" {
  source = "../../modules/s3"

  bucket_name = "dealwise-recordings"
  environment = "staging"
}

# --- Cognito (Auth) --------------------------------------------------------

module "cognito" {
  source = "../../modules/cognito"

  pool_name     = "dealwise"
  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls
  environment   = "staging"
}

# --- ElastiCache (Redis) ---------------------------------------------------

module "elasticache" {
  source = "../../modules/elasticache"

  node_type          = var.redis_node_type
  num_cache_nodes    = 1
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.security_group_ids["cache"]]
  environment        = "staging"
}

# --- ECS (Fargate) ---------------------------------------------------------

module "ecs" {
  source = "../../modules/ecs"

  cluster_name      = "dealwise"
  api_image         = var.api_image
  worker_image      = var.worker_image
  cpu               = var.ecs_cpu
  memory            = var.ecs_memory
  desired_count     = var.ecs_desired_count
  vpc_id            = module.networking.vpc_id
  subnet_ids        = module.networking.private_subnet_ids
  public_subnet_ids = module.networking.public_subnet_ids
  security_group_ids = module.networking.security_group_ids
  environment       = "staging"
}

# --- SQS (Task Queues) ----------------------------------------------------

module "sqs" {
  source = "../../modules/sqs"

  queue_name  = "dealwise-tasks"
  environment = "staging"
}

# --- Monitoring (CloudWatch) -----------------------------------------------

module "monitoring" {
  source = "../../modules/monitoring"

  cluster_name = "dealwise"
  environment  = "staging"
}

# --- Secrets (API Keys) ----------------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  environment = "staging"
}
