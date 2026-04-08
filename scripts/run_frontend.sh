#!/usr/bin/env bash
# ──────────────────────────────────────────────
# run_frontend.sh — Start Vite dev server
# ──────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🌐 Starting Frontend (Vite)..."
echo "   Root: $ROOT_DIR/frontend"
echo ""

cd "$ROOT_DIR/frontend"

# Install dependencies nếu chưa có node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm dependencies..."
    npm install
    echo ""
fi

npx vite --host 0.0.0.0 --port 5173
