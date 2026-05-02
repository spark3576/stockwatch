"""SQLite analysis_cards → 대시보드용 정적 JSON 파일들로 export.

출력:
  dashboard/data/cards.json          — 모든 카드 요약 (목록 인덱스)
  dashboard/data/cards/{id}.json     — 각 카드 상세 (시그널 + 체크 전체)
  dashboard/data/prices/{sym}.json   — OHLCV (TradingView 차트용)
  dashboard/data/manifest.json       — 생성 시각·통계

사용:
  python scripts/export_dashboard.py
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.manager import DB  # noqa: E402

OUT_DIR = ROOT / "docs" / "data"
CARDS_OUT = OUT_DIR / "cards.json"
CARDS_DIR = OUT_DIR / "cards"
PRICES_DIR = OUT_DIR / "prices"
MANIFEST = OUT_DIR / "manifest.json"


def main(price_history_days: int = 365) -> None:
    db = DB()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 기존 카드/가격 폴더 정리 후 재생성
    if CARDS_DIR.exists():
        shutil.rmtree(CARDS_DIR)
    CARDS_DIR.mkdir(parents=True)
    if PRICES_DIR.exists():
        shutil.rmtree(PRICES_DIR)
    PRICES_DIR.mkdir(parents=True)

    # 1. 카드 목록 (최근 100건)
    rows = db.list_cards(limit=200)
    cards_summary: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()  # 종목·시장 — 가장 최근 카드 1건만

    for r in rows:
        sd = json.loads(r.get("signals_json") or "{}")
        td = json.loads(r.get("triggers_json") or "{}")

        symbol = r["symbol"]
        market = r["market"]
        issued = (r.get("issued_at") or "")
        issued_date = issued.split(" ")[0] if " " in issued else issued.split("T")[0]

        key = (symbol, market)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        scores = sd.get("scores", {})
        verdict = td.get("verdict") or sd.get("verdict") or "?"
        risk_level = td.get("risk_level") or sd.get("risk_level") or "?"
        risk_score = td.get("risk_score") or sd.get("risk_score") or 0
        sector = None
        for sig in sd.get("signals") or []:
            if sig.get("signal_type") == "재무 분석":
                sector = (sig.get("details") or {}).get("summary_metrics", {}).get("sector")
                break

        # AI 한줄 요약 우선 (팩트헌터 summary), 없으면 카드 oneliner
        ai_summary = None
        for sig in sd.get("signals") or []:
            if sig.get("signal_type") == "팩트헌터":
                ai_summary = sig.get("summary")
                break

        summary_card: dict = {
            "id": r["id"],
            "symbol": symbol,
            "market": market,
            "name": sd.get("name") or symbol,
            "issued_at": issued,
            "date": issued_date,
            "issue_price": r.get("issue_price"),
            "currency": sd.get("currency"),
            "verdict": verdict,
            "verdict_emoji": _verdict_emoji(verdict),
            "risk_level": risk_level,
            "risk_score": risk_score,
            "scores": {
                "up": scores.get("up", 0),
                "down": scores.get("down", 0),
                "neut": scores.get("neut", 0),
            },
            "summary": sd.get("summary") or "",
            "ai_summary": ai_summary or "",
            "sector": sector or "",
        }
        cards_summary.append(summary_card)

        # 2. 카드 상세 — 전체 signals 포함
        detail = {
            **summary_card,
            "strengths": sd.get("strengths") or [],
            "weaknesses": sd.get("weaknesses") or [],
            "risk_factors": sd.get("risk_factors") or [],
            "signals": sd.get("signals") or [],
        }
        (CARDS_DIR / f"{r['id']}.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    # 시장·날짜 역순 정렬
    cards_summary.sort(key=lambda c: (c["date"], c["symbol"]), reverse=True)
    CARDS_OUT.write_text(
        json.dumps(cards_summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # 4-2. 모든 카드 (전체 시계열용) — 종목당 최신 1건이 아닌 전체
    all_cards: list[dict] = []
    for r in rows:
        sd = json.loads(r.get("signals_json") or "{}")
        td = json.loads(r.get("triggers_json") or "{}")
        symbol = r["symbol"]
        market = r["market"]
        issued = r.get("issued_at") or ""
        issued_date = issued.split(" ")[0] if " " in issued else issued.split("T")[0]
        scores = sd.get("scores", {})
        verdict = td.get("verdict") or sd.get("verdict") or "?"
        all_cards.append({
            "id": r["id"],
            "symbol": symbol,
            "market": market,
            "name": sd.get("name") or symbol,
            "issued_at": issued,
            "date": issued_date,
            "issue_price": r.get("issue_price"),
            "currency": sd.get("currency"),
            "verdict": verdict,
            "verdict_emoji": _verdict_emoji(verdict),
            "risk_level": td.get("risk_level") or "?",
            "risk_score": td.get("risk_score") or 0,
            "scores": {
                "up": scores.get("up", 0),
                "down": scores.get("down", 0),
                "neut": scores.get("neut", 0),
            },
            "summary": sd.get("summary") or "",
            "signals_summary": [
                {
                    "type": s.get("signal_type"),
                    "up": s.get("score_up", 0),
                    "down": s.get("score_down", 0),
                    "neut": s.get("score_neut", 0),
                }
                for s in (sd.get("signals") or [])
            ],
        })
    all_cards.sort(key=lambda c: c["issued_at"], reverse=True)
    (OUT_DIR / "cards_all.json").write_text(
        json.dumps(all_cards, ensure_ascii=False), encoding="utf-8",
    )

    # 3. 가격 시계열 (워치리스트 종목만, 최근 1년)
    watch = db.list_watchlist()
    price_count = 0
    for it in watch:
        df = db.load_prices(it["symbol"], it["market"])
        if df.empty:
            continue
        if price_history_days > 0:
            df = df.tail(price_history_days)
        ohlcv = []
        for idx, row in df.iterrows():
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            ohlcv.append({
                "time": d,
                "open": _safe(row.get("open")),
                "high": _safe(row.get("high")),
                "low": _safe(row.get("low")),
                "close": _safe(row.get("close")),
                "volume": int(_safe(row.get("volume")) or 0),
            })
        out = PRICES_DIR / f"{it['symbol']}_{it['market']}.json"
        out.write_text(
            json.dumps({"symbol": it["symbol"], "market": it["market"], "data": ohlcv},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        price_count += 1

    # 5. 적중률 통계 (card_tracking 테이블 기반)
    accuracy = _compute_accuracy(db)
    (OUT_DIR / "accuracy.json").write_text(
        json.dumps(accuracy, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # 4. 매니페스트
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cards_count": len(cards_summary),
        "prices_count": price_count,
        "version": "v0.4.0",
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    print(f"✅ Export 완료: 카드 {len(cards_summary)}건, 가격 {price_count}건 → {OUT_DIR}")


def _compute_accuracy(db) -> dict:
    """card_tracking + analysis_cards 조인 → 판정별·시그널별 평균 수익률."""
    with db._conn() as conn:
        rows = conn.execute("""
            SELECT ac.id, ac.signals_json, ac.triggers_json,
                   ct.days_after, ct.return_pct
            FROM analysis_cards ac
            JOIN card_tracking ct ON ct.card_id = ac.id
        """).fetchall()

    if not rows:
        return {"by_verdict": {}, "total": 0, "note": "트래킹 데이터 누적 중"}

    # 판정별 N일 후 수익률 집계
    by_verdict: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        try:
            td = json.loads(r[2] or "{}")
            verdict = td.get("verdict") or "?"
        except Exception:
            verdict = "?"
        days = r[3]
        ret = r[4]
        if verdict not in by_verdict:
            by_verdict[verdict] = {}
        key = f"{days}d"
        by_verdict[verdict].setdefault(key, []).append(ret)

    summary: dict[str, dict] = {}
    for v, days_map in by_verdict.items():
        summary[v] = {}
        for d, returns in days_map.items():
            summary[v][d] = {
                "avg": round(sum(returns) / len(returns), 2),
                "min": round(min(returns), 2),
                "max": round(max(returns), 2),
                "n": len(returns),
            }

    return {"by_verdict": summary, "total": len(rows)}


def _verdict_emoji(verdict: str) -> str:
    if "강한 상승" in verdict:
        return "🟢🟢"
    if "상승" in verdict:
        return "🟢"
    if "강한 하락" in verdict:
        return "🔴🔴"
    if "하락" in verdict:
        return "🔴"
    return "🟡"


def _safe(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
