# DealWise AI – Dev Environment Values
# Small instances, single AZ, minimal resources

aws_region = "us-east-1"
vpc_cidr   = "10.0.0.0/16"

# RDS – small instance for development
rds_instance_class    = "db.t3.small"
rds_allocated_storage = 20

# ElastiCache – minimal Redis
redis_node_type = "cache.t3.micro"

# ECS – minimal Fargate resources
ecs_cpu           = 256
ecs_memory        = 512
ecs_desired_count = 1

# Cognito – include Vercel URL once deployed
cognito_callback_urls = ["http://localhost:3000/callback"]
cognito_logout_urls   = ["http://localhost:3000/logout"]

# GitHub – CHANGE THESE to your org/repo
github_org  = "CHANGE_ME"
github_repo = "CHANGE_ME"
