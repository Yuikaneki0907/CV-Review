#!/usr/bin/env bash
# ──────────────────────────────────────────────
# run_all.sh — Start toàn bộ hệ thống CV-Review
#   1. Infrastructure (Docker: DB, Redis, MinIO)
#   2. Backend (FastAPI)
#   3. Worker (Celery)
#   4. Frontend (Vite)
# ──────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$ROOT_DIR/scripts"
CONDA_ENV="cv-review"

cleanup() {
    echo ""
    echo "🛑 Shutting down all services..."
    kill "${PIDS[@]}" 2>/dev/null || true
    wait "${PIDS[@]}" 2>/dev/null || true
    echo "✅ All services stopped."
}
trap cleanup EXIT INT TERM

PIDS=()

# ─── 1. Infrastructure ────────────────────────
echo "🐳 [1/4] Starting infrastructure (DB, Redis, MinIO)..."
cd "$ROOT_DIR"
docker compose up -d db redis minio

echo "⏳ Waiting for PostgreSQL..."
for i in $(seq 1 15); do
    if docker compose exec -T db pg_isready -U cvreview &>/dev/null; then
        echo "✅ PostgreSQL ready"
        break
    fi
    sleep 1
done

# Migrations
if [ -f "$ROOT_DIR/backend/alembic.ini" ]; then
    echo "📦 Running migrations..."
    cd "$ROOT_DIR/backend"
    conda run -n "$CONDA_ENV" --no-capture-output alembic upgrade head 2>/dev/null || true
fi

# ─── 2. Backend ────────────────────────────────
echo ""
echo "🚀 [2/4] Starting FastAPI backend..."
cd "$ROOT_DIR/backend"
conda run -n "$CONDA_ENV" --no-capture-output \
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
PIDS+=($!)

# ─── 3. Worker ─────────────────────────────────
echo "⚙️  [3/4] Starting Celery worker..."
cd "$ROOT_DIR/backend"
conda run -n "$CONDA_ENV" --no-capture-output \
    celery -A app.infrastructure.celery worker --loglevel=info --concurrency=2 &
PIDS+=($!)

# ─── 4. Frontend ───────────────────────────────
echo "🌐 [4/4] Starting Vite frontend..."
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    npm install
fi
npx vite --host 0.0.0.0 --port 5173 &
PIDS+=($!)

# ─── Ready ─────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "  ✅ CV-Review is running!"
echo ""
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  API Docs : http://localhost:8000/docs"
echo "  MinIO UI : http://localhost:9001"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "════════════════════════════════════════════"

wait
