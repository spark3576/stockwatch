"""카드 발행 시점 vs N일 후 가격 트래킹.

모든 카드를 순회, prices_daily에서 발행일 + N일(1/3/7/14/30) 후 가격을 찾아
card_tracking 테이블에 INSERT OR REPLACE.

사용:
  python scripts/track_card_returns.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.manager import DB  # noqa: E402

TRACK_DAYS = [1, 3, 7, 14, 30]


def main() -> None:
    db = DB()
    rows = db.list_cards(limit=500)

    new_count = 0
    update_count = 0

    with db._conn() as conn:
        # card_tracking 테이블 (card_id, days_after) UNIQUE 보장 — 없으면 추가
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracking_unique
            ON card_tracking(card_id, days_after)
        """)

        for r in rows:
            card_id = r["id"]
            symbol = r["symbol"]
            market = r["market"]
            issue_price = r.get("issue_price")
            issued = (r.get("issued_at") or "").split(" ")[0]
            if not issue_price or not issued:
                continue
            try:
                issue_date = datetime.strptime(issued, "%Y-%m-%d").date()
            except ValueError:
                continue

            df = db.load_prices(symbol, market, from_date=issue_date)
            if df.empty:
                continue

            for n in TRACK_DAYS:
                target_date = issue_date + timedelta(days=n)
                # 영업일 기준 가장 가까운 가격 (target_date 이상 첫 행)
                future = df[df.index.date >= target_date] if hasattr(df.index, "date") else df
                if hasattr(df.index, "to_pydatetime"):
                    future = df[df.index.to_pydatetime() >= datetime.combine(target_date, datetime.min.time())]
                if future.empty:
                    continue
                price = float(future["close"].iloc[0])
                return_pct = ((price / issue_price) - 1) * 100

                cur = conn.execute(
                    "SELECT id FROM card_tracking WHERE card_id = ? AND days_after = ?",
                    (card_id, n),
                )
                existing = cur.fetchone()
                if existing:
                    conn.execute(
                        """UPDATE card_tracking
                           SET price = ?, return_pct = ?, checked_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (price, return_pct, existing[0]),
                    )
                    update_count += 1
                else:
                    conn.execute(
                        """INSERT INTO card_tracking (card_id, days_after, price, return_pct)
                           VALUES (?, ?, ?, ?)""",
                        (card_id, n, price, return_pct),
                    )
                    new_count += 1

    print(f"✅ 트래킹 완료: 신규 {new_count}건, 갱신 {update_count}건")


if __name__ == "__main__":
    main()
