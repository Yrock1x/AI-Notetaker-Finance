###############################################################################
# Monitoring Module – CloudWatch log groups, alarms, dashboard
###############################################################################

# --- Log Groups -------------------------------------------------------------

resource "aws_cloudwatch_log_group" "application" {
  name              = "/dealwise/${var.environment}/application"
  retention_in_days = var.environment == "prod" ? 90 : 30

  tags = {
    Name        = "dealwise-${var.environment}-application-logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/dealwise/${var.environment}/access"
  retention_in_days = var.environment == "prod" ? 90 : 30

  tags = {
    Name        = "dealwise-${var.environment}-access-logs"
    Environment = var.environment
  }
}

# --- SNS Topic for Alarm Notifications ------------------------------------

resource "aws_sns_topic" "alarms" {
  name = "dealwise-${var.environment}-alarms"

  tags = {
    Name        = "dealwise-${var.environment}-alarms"
    Environment = var.environment
  }
}

# --- CloudWatch Alarms ------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "dealwise-${var.environment}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "ECS CPU utilization exceeds 80%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    ClusterName = "${var.cluster_name}-${var.environment}"
  }

  tags = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "memory_high" {
  alarm_name          = "dealwise-${var.environment}-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "ECS memory utilization exceeds 80%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    ClusterName = "${var.cluster_name}-${var.environment}"
  }

  tags = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "dealwise-${var.environment}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "ALB 5xx errors exceed threshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Environment = var.environment
  }
}

# --- CloudWatch Dashboard ---------------------------------------------------

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "dealwise-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ECS CPU Utilization"
          metrics = [["AWS/ECS", "CPUUtilization", "ClusterName", "${var.cluster_name}-${var.environment}"]]
          period  = 300
          stat    = "Average"
          region  = data.aws_region.current.name
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ECS Memory Utilization"
          metrics = [["AWS/ECS", "MemoryUtilization", "ClusterName", "${var.cluster_name}-${var.environment}"]]
          period  = 300
          stat    = "Average"
          region  = data.aws_region.current.name
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "RDS CPU Utilization"
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "dealwise-${var.environment}-postgres"]]
          period  = 300
          stat    = "Average"
          region  = data.aws_region.current.name
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "ElastiCache CPU"
          metrics = [["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", "dealwise-${var.environment}-redis"]]
          period  = 300
          stat    = "Average"
          region  = data.aws_region.current.name
          view    = "timeSeries"
        }
      }
    ]
  })
}

# --- Data Sources -----------------------------------------------------------

data "aws_region" "current" {}
