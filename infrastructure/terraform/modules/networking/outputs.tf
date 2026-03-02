output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "security_group_ids" {
  description = "Map of security group IDs"
  value = {
    alb      = aws_security_group.alb.id
    app      = aws_security_group.app.id
    database = aws_security_group.database.id
    cache    = aws_security_group.cache.id
  }
}
