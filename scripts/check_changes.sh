#!/bin/bash
# 시그널 변화 자동 감지 (시간 단위 실행 권장)
#
# 사용법:
#   ./scripts/check_changes.sh
#
# 자동 등록 (장 시간만 30분 단위):
#   0,30 9-15 * * 1-5 /Users/spark/My_project/Claude_Project/stockwatch/scripts/check_changes.sh

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_FILE="$ROOT/logs/cron-$(date +%Y%m%d).log"
mkdir -p "$ROOT/logs"

{
  echo "===== 변화 감지 시작: $(date '+%Y-%m-%d %H:%M:%S') ====="
  "$ROOT/.venv/bin/python" "$ROOT/main.py" report-changes --send --quiet
  echo "===== 완료: $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo ""
} >> "$LOG_FILE" 2>&1
