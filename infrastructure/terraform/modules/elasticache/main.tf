###############################################################################
# ElastiCache Module – Redis cluster for Celery broker & caching
###############################################################################

resource "aws_elasticache_subnet_group" "main" {
  name       = "dealwise-${var.environment}-redis-subnet"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "dealwise-${var.environment}-redis-subnet"
    Environment = var.environment
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "dealwise-${var.environment}-redis"
  description          = "DealWise ${var.environment} Redis cluster"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  port                 = 6379
  parameter_group_name = "default.redis7"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = var.security_group_ids

  # Encryption
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  auth_token                 = var.auth_token

  snapshot_retention_limit = var.environment == "prod" ? 7 : 0

  tags = {
    Name        = "dealwise-${var.environment}-redis"
    Environment = var.environment
  }
}
