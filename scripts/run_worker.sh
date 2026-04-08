#!/usr/bin/env bash
# ──────────────────────────────────────────────
# run_worker.sh — Start Celery worker
# ──────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONDA_ENV="cv-review"

echo "⚙️  Starting Celery worker..."
echo "   Root: $ROOT_DIR/backend"
echo "   Conda: $CONDA_ENV"
echo ""

cd "$ROOT_DIR/backend"

conda run -n "$CONDA_ENV" --no-capture-output \
    celery -A app.infrastructure.celery worker \
    --loglevel=info \
    --concurrency=2
