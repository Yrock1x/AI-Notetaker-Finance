#!/bin/bash
set -euo pipefail

echo "=== Seeding database with sample data ==="

cd backend

if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

python -m scripts.seed

echo "=== Done ==="
