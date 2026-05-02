"""오늘 발행된 카드를 JSON Lines 형식으로 stdout 출력.

cron-triggered Claude 세션이 Notion MCP로 push할 때 사용.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.manager import DB  # noqa: E402

VERDICT_EMOJI = {
    "강한 상승": "🟢🟢 강한 상승",
    "상승 우위": "🟢 상승 우위",
    "약한 상승": "🟢 약한 상승",
    "혼조 / 방향성 불분명": "🟡 혼조",
    "약한 하락": "🔴 약한 하락",
    "하락 우위": "🔴 하락 우위",
    "강한 하락": "🔴🔴 강한 하락",
}

RISK_EMOJI = {
    "낮음": "🟢 낮음",
    "보통": "🟡 보통",
    "높음": "🟠 높음",
    "매우 높음": "🔴 매우 높음",
}

MARKET_EMOJI = {
    "KR": "🇰🇷 KR",
    "US": "🇺🇸 US",
    "JP": "🇯🇵 JP",
    "UK": "🇬🇧 UK",
    "DE": "🇩🇪 DE",
}


def main() -> None:
    db = DB()
    today = datetime.now().strftime("%Y-%m-%d")
    cards_raw = db.list_cards(limit=50)

    seen: set[tuple[str, str]] = set()
    for c in cards_raw:
        # 오늘 발행된 카드만
        if today not in (c.get("issued_at") or ""):
            continue
        key = (c["symbol"], c["market"])
        if key in seen:
            continue
        seen.add(key)

        sd = json.loads(c.get("signals_json") or "{}")
        td = json.loads(c.get("triggers_json") or "{}")

        # 섹터 추출 (재무 분석 시그널 details에서)
        sector = None
        for sig in sd.get("signals", []):
            if sig.get("signal_type") == "재무 분석":
                sector = sig.get("details", {}).get("summary_metrics", {}).get("sector")
                break

        scores = sd.get("scores", {})
        verdict_raw = td.get("verdict", "혼조 / 방향성 불분명")
        risk_raw = td.get("risk_level", "보통")

        out = {
            "종목명": sd.get("name") or c["symbol"],
            "심볼": c["symbol"],
            "시장": MARKET_EMOJI.get(c["market"], c["market"]),
            "date:발행일:start": today,
            "date:발행일:is_datetime": 0,
            "발행가": c["issue_price"],
            "통화": sd.get("currency") or "",
            "종합 판정": VERDICT_EMOJI.get(verdict_raw, f"🟡 {verdict_raw}"),
            "↑": scores.get("up", 0),
            "↓": scores.get("down", 0),
            "△": scores.get("neut", 0),
            "리스크 점수": td.get("risk_score", 0),
            "리스크 레벨": RISK_EMOJI.get(risk_raw, risk_raw),
            "한줄 요약": sd.get("summary") or "",
            "섹터": sector or "",
        }
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
