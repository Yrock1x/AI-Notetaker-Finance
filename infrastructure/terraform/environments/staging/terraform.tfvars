# DealWise AI – Staging Environment Values
# Mid-sized instances, mirrors prod structure at reduced scale

aws_region = "us-east-1"
vpc_cidr   = "10.1.0.0/16"

# RDS – medium instance for staging
rds_instance_class    = "db.t3.medium"
rds_allocated_storage = 50

# ElastiCache – small Redis
redis_node_type = "cache.t3.small"

# ECS – moderate Fargate resources
api_image         = "dealwise/api:latest"
worker_image      = "dealwise/worker:latest"
ecs_cpu           = 512
ecs_memory        = 1024
ecs_desired_count = 2

# Cognito – staging URLs
cognito_callback_urls = ["https://staging.dealwise.ai/callback"]
cognito_logout_urls   = ["https://staging.dealwise.ai/logout"]
