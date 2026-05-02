#!/bin/bash
# 로컬 대시보드 미리보기
#   ./scripts/serve_dashboard.sh
# 브라우저에서 http://localhost:8765 열기

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/docs"

PORT="${1:-8765}"
echo "🌐 StockWatch 대시보드 — http://localhost:$PORT"
echo "    (Ctrl+C 로 중지)"
"$ROOT/.venv/bin/python" -m http.server "$PORT"
