#!/usr/bin/env bash
###############################################################################
# DealWise AI – Populate Secrets Manager
#
# After `terraform apply`, run this script to set the secret values that
# ECS containers need at runtime.
#
# Usage: ./scripts/populate-secrets.sh [dev|staging|prod]
###############################################################################
set -euo pipefail

ENV="${1:-dev}"
REGION="us-east-1"
TF_DIR="infrastructure/terraform/environments/${ENV}"

echo "=== DealWise AI – Secrets Setup (${ENV}) ==="
echo ""

# --- Database URL -----------------------------------------------------------

echo "1) DATABASE_URL"
echo "   RDS password is auto-managed by AWS. To retrieve it:"
echo "   - Go to AWS Console > RDS > dealwise-${ENV}-postgres > Configuration"
echo "   - Click 'Manage master credentials in AWS Secrets Manager'"
echo "   - Copy the password"
echo ""

RDS_ENDPOINT=$(cd "${TF_DIR}" && terraform output -raw rds_endpoint 2>/dev/null || echo "<RDS_ENDPOINT>")

echo "   Then run:"
echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id dealwise/${ENV}/database-url \\"
echo "     --secret-string 'postgresql+asyncpg://dealwise_admin:<PASSWORD>@${RDS_ENDPOINT}/dealwise' \\"
echo "     --region ${REGION}"
echo ""

# --- Redis URL --------------------------------------------------------------

echo "2) REDIS_URL"

REDIS_ENDPOINT=$(cd "${TF_DIR}" && terraform output -raw elasticache_endpoint 2>/dev/null || echo "<REDIS_ENDPOINT>")

echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id dealwise/${ENV}/redis-url \\"
echo "     --secret-string 'rediss://${REDIS_ENDPOINT}:6379/0' \\"
echo "     --region ${REGION}"
echo ""
echo "   Note: If you set a redis_auth_token, use: rediss://:AUTH_TOKEN@${REDIS_ENDPOINT}:6379/0"
echo ""

# --- API Keys ---------------------------------------------------------------

echo "3) API Keys (paste your actual keys)"
echo ""
echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id dealwise/${ENV}/anthropic-api-key \\"
echo "     --secret-string 'sk-ant-...' \\"
echo "     --region ${REGION}"
echo ""
echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id dealwise/${ENV}/openai-api-key \\"
echo "     --secret-string 'sk-...' \\"
echo "     --region ${REGION}"
echo ""
echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id dealwise/${ENV}/assemblyai-api-key \\"
echo "     --secret-string '<DEEPGRAM_API_KEY>' \\"
echo "     --region ${REGION}"
echo ""

# --- App Secret Key ---------------------------------------------------------

APP_SECRET=$(openssl rand -hex 32)
echo "4) App Secret Key (auto-generated)"
echo ""
echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id dealwise/${ENV}/app-secret-key \\"
echo "     --secret-string '${APP_SECRET}' \\"
echo "     --region ${REGION}"
echo ""

echo "=== Done. Run each command above with your actual values. ==="
