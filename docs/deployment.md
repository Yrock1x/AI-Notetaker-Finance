# Deployment Guide

## Infrastructure

DealWise AI deploys to AWS using Terraform.

### AWS Services Used

| Service | Purpose |
|---------|---------|
| ECS Fargate | API server and Celery workers |
| RDS PostgreSQL | Primary database with pgvector |
| ElastiCache Redis | Celery broker and caching |
| S3 | Meeting recordings, documents |
| Cognito | Authentication and SSO |
| SQS | Dead letter queue |
| CloudWatch | Logging and monitoring |
| Secrets Manager | API keys and credentials |
| ALB | Load balancing |

### Environments

- **dev**: Small instances, single AZ
- **staging**: Production-like, multi-AZ
- **prod**: Full scale, multi-AZ, enhanced monitoring

### Deploy

```bash
cd infrastructure/terraform/environments/dev
terraform init
terraform plan
terraform apply
```

## CI/CD

TODO: Configure GitHub Actions for:
1. Run tests on PR
2. Build Docker images on merge to main
3. Deploy to staging automatically
4. Deploy to prod on manual approval
