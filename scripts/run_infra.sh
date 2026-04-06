#!/usr/bin/env bash
# ──────────────────────────────────────────────
# run_infra.sh — Start infrastructure services
#   (PostgreSQL, Redis, MinIO via Docker Compose)
# ──────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🐳 Starting infrastructure services..."
echo ""

cd "$ROOT_DIR"

docker compose up -d db redis minio

echo ""
echo "✅ Infrastructure ready:"
echo "   PostgreSQL : localhost:5432  (user: cvreview)"
echo "   Redis      : localhost:6379"
echo "   MinIO API  : localhost:9000"
echo "   MinIO UI   : localhost:9001  (minioadmin/minioadmin)"
echo ""

# Chờ Postgres sẵn sàng
echo "⏳ Waiting for PostgreSQL..."
for i in $(seq 1 15); do
    if docker compose exec -T db pg_isready -U cvreview &>/dev/null; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    sleep 1
done

# Chạy Alembic migrations nếu có
if [ -f "$ROOT_DIR/backend/alembic.ini" ]; then
    echo ""
    echo "📦 Running database migrations..."
    cd "$ROOT_DIR/backend"
    conda run -n cv-review --no-capture-output alembic upgrade head
    echo "✅ Migrations done."
fi

echo ""
echo "💡 Tiếp theo:"
echo "   ./scripts/run_backend.sh   # FastAPI"
echo "   ./scripts/run_worker.sh    # Celery"
echo "   ./scripts/run_frontend.sh  # Vite"
