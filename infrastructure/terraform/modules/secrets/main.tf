###############################################################################
# Secrets Module – AWS Secrets Manager for API keys & credentials
###############################################################################

resource "aws_secretsmanager_secret" "openai_api_key" {
  name        = "dealwise/${var.environment}/openai-api-key"
  description = "OpenAI API key for DealWise AI"

  tags = {
    Name        = "dealwise-${var.environment}-openai-api-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "dealwise/${var.environment}/anthropic-api-key"
  description = "Anthropic API key for DealWise AI"

  tags = {
    Name        = "dealwise-${var.environment}-anthropic-api-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret" "assemblyai_api_key" {
  name        = "dealwise/${var.environment}/assemblyai-api-key"
  description = "AssemblyAI API key for speech-to-text transcription"

  tags = {
    Name        = "dealwise-${var.environment}-assemblyai-api-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret" "database_url" {
  name        = "dealwise/${var.environment}/database-url"
  description = "PostgreSQL connection string"

  tags = {
    Name        = "dealwise-${var.environment}-database-url"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret" "app_secret_key" {
  name        = "dealwise/${var.environment}/app-secret-key"
  description = "Application secret key for JWT/session signing"

  tags = {
    Name        = "dealwise-${var.environment}-app-secret-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret" "redis_url" {
  name        = "dealwise/${var.environment}/redis-url"
  description = "Redis connection URL for Celery broker and cache"

  tags = {
    Name        = "dealwise-${var.environment}-redis-url"
    Environment = var.environment
  }
}
