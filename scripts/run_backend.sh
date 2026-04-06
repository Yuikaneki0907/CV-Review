#!/usr/bin/env bash
# ──────────────────────────────────────────────
# run_backend.sh — Start FastAPI backend server
# ──────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONDA_ENV="cv-review"

echo "🚀 Starting FastAPI backend..."
echo "   Root: $ROOT_DIR/backend"
echo "   Conda: $CONDA_ENV"
echo ""

cd "$ROOT_DIR/backend"

conda run -n "$CONDA_ENV" --no-capture-output \
    uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
