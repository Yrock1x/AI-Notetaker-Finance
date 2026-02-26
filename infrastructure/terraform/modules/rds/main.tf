###############################################################################
# RDS Module – PostgreSQL with pgvector support
###############################################################################

resource "aws_db_subnet_group" "main" {
  name       = "dealwise-${var.environment}-db-subnet"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "dealwise-${var.environment}-db-subnet"
    Environment = var.environment
  }
}

resource "aws_db_parameter_group" "postgres" {
  name   = "dealwise-${var.environment}-pg-params"
  family = "postgres16"

  parameter {
    name         = "shared_preload_libraries"
    value        = "vector"
    apply_method = "pending-reboot"
  }

  tags = {
    Name        = "dealwise-${var.environment}-pg-params"
    Environment = var.environment
  }
}

resource "aws_db_instance" "main" {
  identifier     = "dealwise-${var.environment}-postgres"
  engine         = "postgres"
  engine_version = "16.3"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 2
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  # Password managed via Secrets Manager; set on first apply or import
  manage_master_user_password = true

  multi_az               = var.environment == "prod" ? true : false
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = var.security_group_ids
  parameter_group_name   = aws_db_parameter_group.postgres.name

  backup_retention_period = var.environment == "prod" ? 30 : 7
  skip_final_snapshot     = var.environment == "prod" ? false : true
  final_snapshot_identifier = var.environment == "prod" ? "dealwise-${var.environment}-final-snapshot" : null
  deletion_protection       = var.environment == "prod" ? true : false

  tags = {
    Name        = "dealwise-${var.environment}-postgres"
    Environment = var.environment
  }
}
