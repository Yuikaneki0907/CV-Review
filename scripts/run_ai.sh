#!/usr/bin/env bash
# ──────────────────────────────────────────────
# run_ai.sh — Start infrastructure services
#   (PostgreSQL, Redis, MinIO via Docker Compose)
# ──────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🐳 Starting infrastructure services (DB, Redis, MinIO)..."
echo "   Docker Compose: $ROOT_DIR/docker-compose.yml"
echo ""

cd "$ROOT_DIR"

# Chỉ khởi động các services hạ tầng, không khởi động backend/worker/frontend
docker compose up -d db redis minio

echo ""
echo "✅ Infrastructure services started:"
echo "   PostgreSQL : localhost:5432"
echo "   Redis      : localhost:6379"
echo "   MinIO      : localhost:9000 (console: localhost:9001)"
echo ""
echo "💡 Tiếp theo, chạy:"
echo "   ./scripts/run_backend.sh   # FastAPI"
echo "   ./scripts/run_worker.sh    # Celery worker"
echo "   ./scripts/run_frontend.sh  # Vite frontend"
