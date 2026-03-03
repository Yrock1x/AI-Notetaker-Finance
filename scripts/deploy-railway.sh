#!/usr/bin/env bash
###############################################################################
# DealWise AI – Railway Deployment
#
# Deploys the API and worker services to Railway.
#
# Prerequisites:
#   - Railway CLI installed: npm i -g @railway/cli
#   - Logged in: railway login
#   - Project linked: railway link (run in backend/)
#   - Environment variables set in Railway dashboard
###############################################################################
set -euo pipefail

cd "$(dirname "$0")/../backend"

# Check Railway CLI
if ! command -v railway &> /dev/null; then
  echo "Error: Railway CLI not installed."
  echo "  Install: npm i -g @railway/cli"
  echo "  Login:   railway login"
  exit 1
fi

echo "==> Running database migrations..."
railway run alembic upgrade head

echo ""
echo "==> Deploying to Railway..."
railway up --detach

echo ""
echo "==> Deployment triggered. Check status at:"
echo "    https://railway.app/dashboard"
echo ""
echo "    Your API will be available at the Railway-provided URL."
echo "    Health check: <RAILWAY_URL>/api/v1/health"
