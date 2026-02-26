###############################################################################
# SQS Module – Task queues with dead letter queue
###############################################################################

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.queue_name}-${var.environment}-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.queue_name}-${var.environment}-dlq"
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "main" {
  name                       = "${var.queue_name}-${var.environment}"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 345600 # 4 days
  visibility_timeout_seconds = 300
  receive_wait_time_seconds  = 10

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "${var.queue_name}-${var.environment}"
    Environment = var.environment
  }
}
