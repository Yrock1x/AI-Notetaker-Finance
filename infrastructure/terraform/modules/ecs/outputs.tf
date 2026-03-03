output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "api_service_name" {
  description = "Name of the API ECS service"
  value       = aws_ecs_service.api.name
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "migrate_task_definition_arn" {
  description = "ARN of the database migration task definition"
  value       = aws_ecs_task_definition.migrate.arn
}

output "private_subnet_ids" {
  description = "Private subnet IDs (pass-through for CD pipeline)"
  value       = var.subnet_ids
}

output "app_security_group_id" {
  description = "App security group ID (pass-through for CD pipeline)"
  value       = var.security_group_ids["app"]
}
