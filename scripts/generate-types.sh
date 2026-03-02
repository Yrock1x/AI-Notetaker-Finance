#!/bin/bash
set -euo pipefail

echo "=== Generating TypeScript types from OpenAPI spec ==="

cd backend

if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# Generate OpenAPI JSON from FastAPI app
python -c "
from app.main import create_app
import json
app = create_app()
spec = app.openapi()
with open('../shared/openapi.json', 'w') as f:
    json.dump(spec, f, indent=2)
print('OpenAPI spec written to shared/openapi.json')
"

cd ../frontend

# Generate TypeScript types from OpenAPI spec (requires openapi-typescript)
npx openapi-typescript ../shared/openapi.json -o src/types/generated.ts 2>/dev/null || \
    echo "Install openapi-typescript: npm i -D openapi-typescript"

echo "=== Done ==="
