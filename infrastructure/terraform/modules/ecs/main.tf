###############################################################################
# ECS Module – Fargate cluster, task definitions, ALB
###############################################################################

# --- ECS Cluster ------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "${var.cluster_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.cluster_name}-${var.environment}"
    Environment = var.environment
  }
}

# --- CloudWatch Log Groups --------------------------------------------------

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.cluster_name}-${var.environment}/api"
  retention_in_days = 30

  tags = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.cluster_name}-${var.environment}/worker"
  retention_in_days = 30

  tags = {
    Environment = var.environment
  }
}

# --- IAM Roles --------------------------------------------------------------

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.cluster_name}-${var.environment}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name               = "${var.cluster_name}-${var.environment}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = {
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "ecs_task" {
  # S3 access for file uploads/downloads
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      var.s3_bucket_arn,
      "${var.s3_bucket_arn}/*",
    ]
  }

  # Secrets Manager for app secrets
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = [
      "arn:aws:secretsmanager:${data.aws_region.current.name}:*:secret:dealwise/${var.environment}/*",
    ]
  }

  # KMS for decrypting secrets and S3 objects
  statement {
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values = [
        "secretsmanager.${data.aws_region.current.name}.amazonaws.com",
        "s3.${data.aws_region.current.name}.amazonaws.com",
      ]
    }
  }

  # CloudWatch Logs for application logging
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "${aws_cloudwatch_log_group.api.arn}:*",
      "${aws_cloudwatch_log_group.worker.arn}:*",
    ]
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  name   = "${var.cluster_name}-${var.environment}-task-policy"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task.json
}

# --- Task Definitions -------------------------------------------------------

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.cluster_name}-${var.environment}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }

      environment = [
        { name = "ENVIRONMENT", value = var.environment }
      ]
    }
  ])

  tags = {
    Name        = "${var.cluster_name}-${var.environment}-api"
    Environment = var.environment
  }
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.cluster_name}-${var.environment}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = var.worker_image
      essential = true

      command = ["celery", "-A", "dealwise.celery", "worker", "--loglevel=info"]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "worker"
        }
      }

      environment = [
        { name = "ENVIRONMENT", value = var.environment }
      ]
    }
  ])

  tags = {
    Name        = "${var.cluster_name}-${var.environment}-worker"
    Environment = var.environment
  }
}

# --- Data Sources -----------------------------------------------------------

data "aws_region" "current" {}

# --- Application Load Balancer ----------------------------------------------

resource "aws_lb" "main" {
  name               = "${var.cluster_name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.security_group_ids["alb"]]
  subnets            = var.public_subnet_ids

  tags = {
    Name        = "${var.cluster_name}-${var.environment}-alb"
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "api" {
  name        = "${var.cluster_name}-${var.environment}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/api/v1/health"
    matcher             = "200"
  }

  tags = {
    Name        = "${var.cluster_name}-${var.environment}-api-tg"
    Environment = var.environment
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- ECS Services -----------------------------------------------------------

resource "aws_ecs_service" "api" {
  name            = "${var.cluster_name}-${var.environment}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_ids["app"]]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]

  tags = {
    Name        = "${var.cluster_name}-${var.environment}-api"
    Environment = var.environment
  }
}

resource "aws_ecs_service" "worker" {
  name            = "${var.cluster_name}-${var.environment}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_ids["app"]]
    assign_public_ip = false
  }

  tags = {
    Name        = "${var.cluster_name}-${var.environment}-worker"
    Environment = var.environment
  }
}
