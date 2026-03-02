# DealWise AI – Production Environment Values
# Production-grade instances, multi-AZ, high availability

aws_region = "us-east-1"
vpc_cidr   = "10.2.0.0/16"

# RDS – production-grade instance, multi-AZ enabled in module
rds_instance_class    = "db.r6g.large"
rds_allocated_storage = 100

# ElastiCache – production Redis with replication
redis_node_type = "cache.r6g.large"

# ECS – production Fargate resources
api_image         = "dealwise/api:latest"
worker_image      = "dealwise/worker:latest"
ecs_cpu           = 1024
ecs_memory        = 2048
ecs_desired_count = 3

# Cognito – production URLs
cognito_callback_urls = ["https://app.dealwise.ai/callback"]
cognito_logout_urls   = ["https://app.dealwise.ai/logout"]
