#!/bin/bash
# 매일 아침 자동 데일리 리포트 (cron / launchd 용)
#
# 사용법:
#   chmod +x scripts/daily_report.sh
#   ./scripts/daily_report.sh
#
# 자동 등록 예시 (macOS launchd 또는 cron):
#   crontab -e
#   30 8 * * 1-5 /Users/spark/My_project/Claude_Project/stockwatch/scripts/daily_report.sh

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_FILE="$ROOT/logs/cron-$(date +%Y%m%d).log"
mkdir -p "$ROOT/logs"

{
  echo "===== 데일리 리포트 시작: $(date '+%Y-%m-%d %H:%M:%S') ====="
  "$ROOT/.venv/bin/python" "$ROOT/main.py" report-daily --send
  echo "===== 완료: $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo ""
} >> "$LOG_FILE" 2>&1
