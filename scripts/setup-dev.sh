#!/bin/bash
set -euo pipefail

echo "=== DealWise AI - Development Setup ==="
echo ""

# Backend setup
echo ">> Setting up backend..."
cd backend

if [ ! -d ".venv" ]; then
    python -m venv .venv
    echo "   Created virtual environment"
fi

# Activate venv (cross-platform)
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

pip install -e ".[dev]" --quiet
echo "   Installed Python dependencies"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   Created .env from .env.example"
fi

cd ..

# Frontend setup
echo ""
echo ">> Setting up frontend..."
cd frontend
npm install --silent
echo "   Installed Node dependencies"

if [ ! -f ".env.local" ]; then
    echo "NEXT_PUBLIC_API_URL=/api/v1" > .env.local
    echo "   Created .env.local"
fi

cd ..

# Docker services
echo ""
echo ">> Starting Docker services (Postgres, Redis, MinIO)..."
cd backend
docker compose up -d postgres redis minio

echo ""
echo ">> Waiting for Postgres to be ready..."
sleep 5

echo ">> Running database migrations..."
alembic upgrade head || echo "   (Migrations skipped - run manually if needed)"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Start the backend:  cd backend && uvicorn app.main:create_app --factory --port 8000 --reload"
echo "Start the worker:   cd backend && celery -A app.tasks.celery_app worker --loglevel=info"
echo "Start the frontend: cd frontend && npm run dev"
echo ""
echo "API docs:     http://localhost:8000/docs"
echo "Frontend:     http://localhost:3000"
echo "Flower:       http://localhost:5555"
echo "MinIO:        http://localhost:9001"
