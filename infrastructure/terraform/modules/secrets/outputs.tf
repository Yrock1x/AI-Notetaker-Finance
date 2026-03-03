output "secret_arns" {
  description = "Map of secret ARNs"
  value = {
    openai_api_key     = aws_secretsmanager_secret.openai_api_key.arn
    anthropic_api_key  = aws_secretsmanager_secret.anthropic_api_key.arn
    assemblyai_api_key = aws_secretsmanager_secret.assemblyai_api_key.arn
    database_url       = aws_secretsmanager_secret.database_url.arn
    app_secret_key     = aws_secretsmanager_secret.app_secret_key.arn
    redis_url          = aws_secretsmanager_secret.redis_url.arn
  }
}
