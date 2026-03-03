#!/usr/bin/env bash
###############################################################################
# DealWise AI – AWS Bootstrap
#
# Creates the S3 bucket and DynamoDB table required by Terraform's S3 backend.
# Run this ONCE before the first `terraform init`.
#
# Prerequisites:
#   - AWS CLI installed and configured (`aws configure`)
#   - IAM permissions: s3:*, dynamodb:*
###############################################################################
set -euo pipefail

REGION="us-east-1"
STATE_BUCKET="dealwise-terraform-state"
LOCK_TABLE="dealwise-terraform-lock"

echo "==> Creating Terraform state bucket: ${STATE_BUCKET}"
aws s3api create-bucket \
  --bucket "${STATE_BUCKET}" \
  --region "${REGION}"

aws s3api put-bucket-versioning \
  --bucket "${STATE_BUCKET}" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "${STATE_BUCKET}" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms"
      }
    }]
  }'

aws s3api put-public-access-block \
  --bucket "${STATE_BUCKET}" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "==> Creating Terraform lock table: ${LOCK_TABLE}"
aws dynamodb create-table \
  --table-name "${LOCK_TABLE}" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}"

echo ""
echo "Bootstrap complete. You can now run:"
echo "  cd infrastructure/terraform/environments/dev"
echo "  terraform init"
echo "  terraform plan"
echo "  terraform apply"
