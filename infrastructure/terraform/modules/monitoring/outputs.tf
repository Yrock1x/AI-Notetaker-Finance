output "log_group_names" {
  description = "List of CloudWatch log group names"
  value = [
    aws_cloudwatch_log_group.application.name,
    aws_cloudwatch_log_group.access.name,
  ]
}
