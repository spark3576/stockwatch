"""AI 시그널 결과 JSON Lines를 stdin으로 받아 SQLite ai_signals 테이블에 저장.

각 줄 형식:
{
  "symbol": "005930",
  "market": "KR",
  "signal_type": "fact_hunter",
  "summary": "한 줄 요약",
  "checks": [
    {"name": "...", "verdict": "↑|↓|△", "reason": "..."},
    ...
  ],
  ... (기타 메타)
}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.manager import DB  # noqa: E402


def main() -> None:
    db = DB()
    saved = 0
    failed = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[skip] JSON 파싱 실패: {e}", file=sys.stderr)
            failed += 1
            continue

        symbol = r.get("symbol")
        market = r.get("market")
        signal_type = r.get("signal_type")
        if not (symbol and market and signal_type):
            print(f"[skip] 필수 필드 누락: {r}", file=sys.stderr)
            failed += 1
            continue

        checks = r.get("checks") or []
        up = sum(1 for c in checks if c.get("verdict") == "↑")
        down = sum(1 for c in checks if c.get("verdict") == "↓")
        neut = sum(1 for c in checks if c.get("verdict") == "△")

        summary = r.get("summary", "")
        # 전체 응답을 payload에 저장
        payload = {k: v for k, v in r.items() if k not in ("symbol", "market", "signal_type")}

        db.save_ai_signal(
            symbol=symbol, market=market, signal_type=signal_type,
            score_up=up, score_down=down, score_neut=neut,
            summary=summary, payload=payload,
        )
        saved += 1
        print(f"[saved] {symbol} ({market}) {signal_type}: ↑{up} ↓{down} △{neut}", file=sys.stderr)

    print(f"\n총 {saved}건 저장, {failed}건 실패", file=sys.stderr)


if __name__ == "__main__":
    main()
