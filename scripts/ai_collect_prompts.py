"""워치리스트 종목들의 AI 시그널 프롬프트를 파일에 JSON Lines로 출력.

사용법:
  python scripts/ai_collect_prompts.py [출력_파일_경로]
  (인자 없으면 /tmp/ai_prompts.jsonl)

cokacdir cron Claude 세션이 이 파일을 읽어 각 프롬프트에 분석 결과 JSON을 생성.
이후 ai_save_results.py로 결과를 DB에 저장.

JSON 라인 형식:
{
  "symbol": "005930",
  "market": "KR",
  "signal_type": "fact_hunter|why_engine|global_macro",
  "prompt": "..."
}
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# pykrx 등 stdout으로 직접 출력하는 라이브러리 억제용 버퍼
_silenced = StringIO()


def emit(fh, data: dict) -> None:
    fh.write(json.dumps(data, ensure_ascii=False) + "\n")
    fh.flush()


def main() -> None:
    output_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ai_prompts.jsonl"

    # 모든 import + 데이터 수집을 stdout 억제 컨텍스트에서 실행
    with redirect_stdout(_silenced):
        from src.ai.prompts import (
            build_fact_hunter_prompt,
            build_global_macro_prompt,
            build_why_engine_prompt,
        )
        from src.collectors.calendar_data import days_until
        from src.collectors.fundamentals import fetch_fundamentals
        from src.collectors.market_index import fetch_market_index
        from src.collectors.news import fetch_news
        from src.collectors.unified import collect_history, collect_info
        from src.db.manager import DB
        from src.signals.event_tracker import (
            FOMC_DATES_2026, _next_cpi_date, _next_macro_date,
        )
        from src.utils.markets import market_info

        db = DB()
        items = db.list_watchlist()

        prompts: list[dict] = []
        for it in items:
            sym = it["symbol"]
            market = it["market"]
            info = collect_info(sym)
            df, _ = collect_history(sym, days=60)
            if df.empty:
                continue
            name = info.get("name") or sym
            mi = market_info(market)

            close = df["close"].astype(float)
            last_price = float(close.iloc[-1])
            change_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) >= 6 else 0
            change_3d = ((close.iloc[-1] / close.iloc[-4]) - 1) * 100 if len(close) >= 4 else 0
            change_today = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0

            vol = df.get("volume")
            vol_ratio = 1.0
            if vol is not None and len(vol) >= 6:
                avg5 = float(vol.iloc[-6:-1].mean())
                if avg5 > 0:
                    vol_ratio = float(vol.iloc[-1]) / avg5

            idx_df = fetch_market_index(market, days=20)
            market_change_today = None
            market_change_5d = None
            if not idx_df.empty:
                ic = idx_df["close"].astype(float)
                if len(ic) >= 2:
                    market_change_today = ((ic.iloc[-1] / ic.iloc[-2]) - 1) * 100
                if len(ic) >= 6:
                    market_change_5d = ((ic.iloc[-1] / ic.iloc[-6]) - 1) * 100

            fund = fetch_fundamentals(sym)
            sector = fund.get("sector")

            news_72h = fetch_news(sym, max_items=10, days=3)

            next_fomc = _next_macro_date(FOMC_DATES_2026)
            next_cpi = _next_cpi_date()
            d_fomc = days_until(next_fomc) if next_fomc else None
            d_cpi = days_until(next_cpi) if next_cpi else None

            # 1) Fact Hunter
            prompts.append({
                "symbol": sym, "market": market, "signal_type": "fact_hunter",
                "prompt": build_fact_hunter_prompt(
                    name=name, symbol=sym, market=market,
                    price=last_price, currency=mi.currency,
                    change_5d_pct=change_5d, news=news_72h,
                ),
            })

            # 2) Why Engine — 의미있는 변동만
            if abs(change_today) >= 1.0 or abs(change_3d) >= 2.5:
                prompts.append({
                    "symbol": sym, "market": market, "signal_type": "why_engine",
                    "prompt": build_why_engine_prompt(
                        name=name, symbol=sym, market=market,
                        today_change_pct=change_today, change_3d_pct=change_3d,
                        today_volume_ratio=vol_ratio,
                        market_change_pct=market_change_today,
                        sector_change_pct=None,
                        news=news_72h,
                    ),
                })

            # 3) Global Macro
            prompts.append({
                "symbol": sym, "market": market, "signal_type": "global_macro",
                "prompt": build_global_macro_prompt(
                    name=name, symbol=sym, market=market, sector=sector,
                    market_index_change_5d=market_change_5d,
                    fomc_d_day=d_fomc, cpi_d_day=d_cpi,
                    related_news=news_72h,
                ),
            })

    # 파일 출력
    with open(output_file, "w", encoding="utf-8") as out:
        for p in prompts:
            emit(out, p)

    print(f"✅ AI 프롬프트 {len(prompts)}건 생성: {output_file}")


if __name__ == "__main__":
    main()
