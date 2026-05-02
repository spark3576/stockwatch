-- StockWatch SQLite 스키마 (Phase 1)
-- TimescaleDB는 Phase 4 이상에서 마이그레이션

-- 종목 마스터
CREATE TABLE IF NOT EXISTS securities (
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,           -- KR/US/JP/UK/DE
    name        TEXT,
    sector      TEXT,
    industry    TEXT,
    currency    TEXT,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, market)
);

-- 일봉 OHLCV (시계열)
CREATE TABLE IF NOT EXISTS prices_daily (
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    date        DATE NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    PRIMARY KEY (symbol, market, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_daily_date ON prices_daily(date DESC);

-- 시그널 결과 (스냅샷)
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    signal_type TEXT NOT NULL,           -- chart_signal / chart_pattern / ...
    score_up    INTEGER DEFAULT 0,       -- ↑ 갯수
    score_down  INTEGER DEFAULT 0,       -- ↓ 갯수
    score_neut  INTEGER DEFAULT 0,       -- △ 갯수
    payload     TEXT,                    -- JSON: 상세 근거
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol, market, generated_at DESC);

-- AI 분석 카드 (Phase 3+)
CREATE TABLE IF NOT EXISTS analysis_cards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    issued_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issue_price REAL,                    -- 발행 시 가격
    summary     TEXT,                    -- AI 종합 요약
    signals_json TEXT,                   -- 8개 시그널 종합
    news_json   TEXT,                    -- 핵심 뉴스 3개
    triggers_json TEXT,                  -- 알림 트리거 (가격 등)
    model_used  TEXT,                    -- claude-opus-4-7 등
    locked      INTEGER DEFAULT 1        -- 1=immutable
);
CREATE INDEX IF NOT EXISTS idx_cards_symbol ON analysis_cards(symbol, market, issued_at DESC);

-- 카드 시계열 트래킹 (Phase 5)
CREATE TABLE IF NOT EXISTS card_tracking (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     INTEGER NOT NULL,
    checked_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    days_after  INTEGER,                 -- 발행 후 N일
    price       REAL,
    return_pct  REAL,
    FOREIGN KEY (card_id) REFERENCES analysis_cards(id)
);

-- 알림 이력
CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    channel     TEXT,                    -- telegram
    chat_id     TEXT,
    kind        TEXT,                    -- daily / signal / manual
    payload     TEXT,
    success     INTEGER DEFAULT 1
);

-- 워치리스트 (Phase 2)
CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    alias       TEXT,                    -- 별명 (예: "장기보유 1")
    enabled     INTEGER DEFAULT 1,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_analyzed_at TIMESTAMP,
    UNIQUE(symbol, market)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_enabled ON watchlist(enabled);

-- AI 시그널 결과 캐시 (Phase 3)
-- cokacdir cron Claude 세션이 채워주고 Python 시그널이 읽음
CREATE TABLE IF NOT EXISTS ai_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    market          TEXT NOT NULL,
    signal_type     TEXT NOT NULL,       -- fact_hunter / why_engine / global_macro
    score_up        INTEGER DEFAULT 0,
    score_down      INTEGER DEFAULT 0,
    score_neut      INTEGER DEFAULT 0,
    summary         TEXT,
    payload         TEXT,                 -- JSON: {checks: [...], raw_news: [...], etc}
    generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ai_signals_lookup
    ON ai_signals(symbol, market, signal_type, generated_at DESC);

-- 사용자 정의 알림 트리거 (Phase 2)
CREATE TABLE IF NOT EXISTS alert_triggers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    market          TEXT NOT NULL,
    trigger_type    TEXT NOT NULL,       -- price_above / price_below / verdict_change
    trigger_value   TEXT,                 -- 숫자(가격) 또는 조건
    note            TEXT,
    enabled         INTEGER DEFAULT 1,
    last_triggered_at TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_triggers_enabled ON alert_triggers(enabled);
