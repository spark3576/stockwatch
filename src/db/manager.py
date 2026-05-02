"""SQLite DB 매니저."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.utils.logger import logger

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "stockwatch.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class DB:
    """단순 SQLite 매니저 (Phase 1)."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # --- init ---
    def init_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._conn() as c:
            c.executescript(sql)
        logger.info(f"DB 스키마 초기화 완료 → {self.db_path}")

    # --- securities ---
    def upsert_security(
        self,
        symbol: str,
        market: str,
        name: str | None = None,
        sector: str | None = None,
        industry: str | None = None,
        currency: str | None = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO securities (symbol, market, name, sector, industry, currency, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(symbol, market) DO UPDATE SET
                    name=excluded.name,
                    sector=excluded.sector,
                    industry=excluded.industry,
                    currency=excluded.currency,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (symbol, market, name, sector, industry, currency),
            )

    # --- prices ---
    def insert_prices(self, symbol: str, market: str, df: pd.DataFrame) -> int:
        """OHLCV DataFrame을 prices_daily 테이블에 INSERT OR REPLACE.

        df 인덱스는 DatetimeIndex, 컬럼: open/high/low/close/volume
        """
        if df.empty:
            return 0
        rows: list[tuple] = []
        for idx, row in df.iterrows():
            d = idx.date() if hasattr(idx, "date") else idx
            rows.append(
                (
                    symbol,
                    market,
                    d.isoformat(),
                    _safe_float(row.get("open")),
                    _safe_float(row.get("high")),
                    _safe_float(row.get("low")),
                    _safe_float(row.get("close")),
                    _safe_int(row.get("volume")),
                )
            )
        with self._conn() as c:
            c.executemany(
                """
                INSERT OR REPLACE INTO prices_daily
                  (symbol, market, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def load_prices(
        self,
        symbol: str,
        market: str,
        from_date: date | str | None = None,
        to_date: date | str | None = None,
    ) -> pd.DataFrame:
        q = "SELECT date, open, high, low, close, volume FROM prices_daily WHERE symbol = ? AND market = ?"
        params: list[Any] = [symbol, market]
        if from_date:
            q += " AND date >= ?"
            params.append(str(from_date))
        if to_date:
            q += " AND date <= ?"
            params.append(str(to_date))
        q += " ORDER BY date ASC"
        with self._conn() as c:
            df = pd.read_sql_query(q, c, params=params, parse_dates=["date"])
        if not df.empty:
            df = df.set_index("date")
        return df

    # --- signals ---
    def insert_signal(
        self,
        symbol: str,
        market: str,
        signal_type: str,
        score_up: int = 0,
        score_down: int = 0,
        score_neut: int = 0,
        payload: dict | None = None,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO signals (symbol, market, signal_type, score_up, score_down, score_neut, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    market,
                    signal_type,
                    score_up,
                    score_down,
                    score_neut,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            )
            return cur.lastrowid or 0

    # --- composite cards (Step 1D) ---
    def save_composite_card(self, card_dict: dict) -> int:
        """CompositeCard.to_dict() 결과를 analysis_cards 테이블에 저장."""
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO analysis_cards
                  (symbol, market, issue_price, summary, signals_json, triggers_json, model_used, locked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card_dict["symbol"],
                    card_dict["market"],
                    card_dict["issue_price"],
                    card_dict.get("summary", ""),
                    json.dumps(card_dict, ensure_ascii=False),
                    json.dumps({
                        "verdict": card_dict.get("verdict"),
                        "risk_score": card_dict.get("risk_score"),
                        "risk_level": card_dict.get("risk_level"),
                    }, ensure_ascii=False),
                    "rule-based-v1",
                    1,
                ),
            )
            return cur.lastrowid or 0

    def list_cards(self, symbol: str | None = None, limit: int = 20) -> list[dict]:
        """저장된 카드 목록 조회 (최신순)."""
        q = """
            SELECT id, symbol, market, issued_at, issue_price, summary, signals_json, triggers_json
            FROM analysis_cards
        """
        params: list[Any] = []
        if symbol:
            q += " WHERE symbol = ?"
            params.append(symbol)
        q += " ORDER BY issued_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            cur = c.execute(q, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return rows

    # --- AI 시그널 캐시 (Phase 3) ---
    def get_latest_ai_signal(
        self, symbol: str, market: str, signal_type: str, max_age_hours: int = 24,
    ) -> dict | None:
        """최근 AI 시그널 결과 조회 (max_age_hours 이내). 없거나 오래되면 None."""
        with self._conn() as c:
            cur = c.execute(
                """
                SELECT score_up, score_down, score_neut, summary, payload, generated_at
                FROM ai_signals
                WHERE symbol = ? AND market = ? AND signal_type = ?
                  AND datetime(generated_at) > datetime('now', ?)
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                (symbol, market, signal_type, f"-{max_age_hours} hours"),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "score_up": row[0], "score_down": row[1], "score_neut": row[2],
                "summary": row[3] or "", "payload": json.loads(row[4] or "{}"),
                "generated_at": row[5],
            }

    def save_ai_signal(
        self, symbol: str, market: str, signal_type: str,
        score_up: int, score_down: int, score_neut: int,
        summary: str = "", payload: dict | None = None,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO ai_signals
                  (symbol, market, signal_type, score_up, score_down, score_neut, summary, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol, market, signal_type,
                    score_up, score_down, score_neut,
                    summary, json.dumps(payload or {}, ensure_ascii=False),
                ),
            )
            return cur.lastrowid or 0

    # --- watchlist (Phase 2) ---
    def add_watchlist(self, symbol: str, market: str, alias: str | None = None) -> int:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO watchlist (symbol, market, alias) VALUES (?, ?, ?)
                ON CONFLICT(symbol, market) DO UPDATE SET
                    alias = COALESCE(excluded.alias, watchlist.alias),
                    enabled = 1
                """,
                (symbol, market, alias),
            )
            return cur.lastrowid or 0

    def remove_watchlist(self, symbol: str, market: str | None = None) -> int:
        with self._conn() as c:
            if market:
                cur = c.execute(
                    "DELETE FROM watchlist WHERE symbol = ? AND market = ?",
                    (symbol, market),
                )
            else:
                cur = c.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
            return cur.rowcount

    def list_watchlist(self, only_enabled: bool = True) -> list[dict]:
        q = """SELECT symbol, market, alias, enabled, added_at, last_analyzed_at
               FROM watchlist"""
        if only_enabled:
            q += " WHERE enabled = 1"
        q += " ORDER BY added_at ASC"
        with self._conn() as c:
            cur = c.execute(q)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def update_watchlist_analyzed(self, symbol: str, market: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE watchlist SET last_analyzed_at = CURRENT_TIMESTAMP WHERE symbol=? AND market=?",
                (symbol, market),
            )

    # --- alert triggers (Phase 2) ---
    def add_trigger(
        self, symbol: str, market: str, trigger_type: str,
        trigger_value: str | None = None, note: str | None = None,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO alert_triggers
                   (symbol, market, trigger_type, trigger_value, note)
                   VALUES (?, ?, ?, ?, ?)""",
                (symbol, market, trigger_type, trigger_value, note),
            )
            return cur.lastrowid or 0

    def list_triggers(self, symbol: str | None = None, only_enabled: bool = True) -> list[dict]:
        q = "SELECT * FROM alert_triggers"
        params: list[Any] = []
        conds: list[str] = []
        if symbol:
            conds.append("symbol = ?")
            params.append(symbol)
        if only_enabled:
            conds.append("enabled = 1")
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY created_at DESC"
        with self._conn() as c:
            cur = c.execute(q, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def remove_trigger(self, trigger_id: int) -> int:
        with self._conn() as c:
            cur = c.execute("DELETE FROM alert_triggers WHERE id = ?", (trigger_id,))
            return cur.rowcount

    def mark_trigger_fired(self, trigger_id: int) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE alert_triggers SET last_triggered_at = CURRENT_TIMESTAMP WHERE id = ?",
                (trigger_id,),
            )

    # --- notifications ---
    def log_notification(
        self,
        channel: str,
        chat_id: str,
        kind: str,
        payload: dict,
        success: bool = True,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO notifications (channel, chat_id, kind, payload, success)
                VALUES (?, ?, ?, ?, ?)
                """,
                (channel, chat_id, kind, json.dumps(payload, ensure_ascii=False), int(success)),
            )


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    f = _safe_float(v)
    if f is None:
        return None
    return int(f)


__all__ = ["DB", "DB_PATH"]
