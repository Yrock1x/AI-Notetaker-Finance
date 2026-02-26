# DealWise AI

Meeting intelligence platform for investment banking, private equity, and venture capital professionals.

## Architecture

- **Backend**: Python (FastAPI) — `backend/`
- **Frontend**: Next.js (React) — `frontend/`
- **Infrastructure**: Terraform (AWS) — `infrastructure/`
- **Shared**: Constants and schemas — `shared/`

## Quick Start

```bash
# 1. Start infrastructure services
cd backend && docker compose up -d postgres redis minio

# 2. Set up backend
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv/Scripts/activate on Windows
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:create_app --factory --port 8000 --reload

# 3. Set up frontend
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## Development

- Backend API docs: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Flower (Celery monitoring): http://localhost:5555
- MinIO console: http://localhost:9001
