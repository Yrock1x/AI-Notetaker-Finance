output "deploy_role_arn" {
  description = "ARN of the GitHub Actions deploy role"
  value       = aws_iam_role.github_deploy.arn
}
