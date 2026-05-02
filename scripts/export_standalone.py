"""자체완결 단일 HTML 대시보드 v2 — 시각화 중심.

캔들차트 + 레이더 차트 + 스파크라인 + 점수 바 + 리스크 게이지 임베드.
모든 데이터·차트 라이브러리·UI가 1개 HTML 파일에 들어감.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.manager import DB  # noqa: E402

OUT = ROOT / "docs" / "standalone.html"
PRICE_DAYS = 180


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


def main() -> None:
    db = DB()
    rows = db.list_cards(limit=200)

    cards: list[dict] = []
    seen: set[tuple[str, str]] = set()    # 종목당 최신 1건만 (분석 시점 다른 카드는 별도 시계열 페이지에서)
    prices_data: dict[str, list[dict]] = {}

    for r in rows:
        sd = json.loads(r.get("signals_json") or "{}")
        td = json.loads(r.get("triggers_json") or "{}")
        symbol = r["symbol"]
        market = r["market"]
        issued = r.get("issued_at") or ""
        date = issued.split(" ")[0] if " " in issued else issued.split("T")[0]
        key = (symbol, market)
        if key in seen:
            continue
        seen.add(key)

        scores = sd.get("scores", {})
        verdict = td.get("verdict") or "?"
        risk_level = td.get("risk_level") or "?"
        risk_score = td.get("risk_score") or 0
        sector = None
        for sig in sd.get("signals") or []:
            if sig.get("signal_type") == "재무 분석":
                sector = (sig.get("details") or {}).get("summary_metrics", {}).get("sector")
                break

        cards.append({
            "id": r["id"],
            "symbol": symbol,
            "market": market,
            "name": sd.get("name") or symbol,
            "date": date,
            "issued_at": issued,
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
            "sector": sector or "",
            "strengths": sd.get("strengths") or [],
            "weaknesses": sd.get("weaknesses") or [],
            "risk_factors": sd.get("risk_factors") or [],
            "signals": sd.get("signals") or [],
        })

        # 가격 데이터 — 종목 1회만
        sym_key = f"{symbol}_{market}"
        if sym_key not in prices_data:
            df = db.load_prices(symbol, market)
            if not df.empty:
                df_t = df.tail(PRICE_DAYS)
                ohlcv = []
                for idx, row in df_t.iterrows():
                    d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                    open_v = row.get("open")
                    high_v = row.get("high")
                    low_v = row.get("low")
                    close_v = row.get("close")
                    vol_v = row.get("volume")
                    if close_v is None:
                        continue
                    ohlcv.append({
                        "time": d,
                        "open": float(open_v) if open_v is not None else float(close_v),
                        "high": float(high_v) if high_v is not None else float(close_v),
                        "low": float(low_v) if low_v is not None else float(close_v),
                        "close": float(close_v),
                        "volume": int(vol_v) if vol_v is not None else 0,
                    })
                prices_data[sym_key] = ohlcv

    cards.sort(key=lambda c: (c["date"], c["symbol"]), reverse=True)

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards_json = json.dumps(cards, ensure_ascii=False)
    prices_json = json.dumps(prices_data, ensure_ascii=False)

    html = (HTML_TEMPLATE
            .replace("__CARDS_DATA__", cards_json)
            .replace("__PRICES_DATA__", prices_json)
            .replace("__GEN_TIME__", generated)
            .replace("__COUNT__", str(len(cards))))
    OUT.write_text(html, encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"✅ 단일 파일 생성: {OUT} ({size_kb:.1f} KB, {len(cards)}개 카드, {len(prices_data)}개 가격)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 StockWatch — 분석 카드</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', system-ui, sans-serif; }
  .stock-card { transition: transform 0.15s, box-shadow 0.15s; }
  .stock-card:hover { transform: translateY(-2px); box-shadow: 0 10px 30px -10px rgba(59,130,246,0.3); }
  .v-strong-up    { border-left: 4px solid #10b981; }
  .v-up           { border-left: 4px solid #34d399; }
  .v-weak-up      { border-left: 4px solid #6ee7b7; }
  .v-mixed        { border-left: 4px solid #facc15; }
  .v-weak-down    { border-left: 4px solid #fb923c; }
  .v-down         { border-left: 4px solid #f87171; }
  .v-strong-down  { border-left: 4px solid #ef4444; }
  .b-strong-up    { background: #064e3b; color: #6ee7b7; }
  .b-up           { background: #065f46; color: #a7f3d0; }
  .b-weak-up      { background: #134e4a; color: #99f6e4; }
  .b-mixed        { background: #422006; color: #fde68a; }
  .b-weak-down    { background: #431407; color: #fed7aa; }
  .b-down         { background: #7f1d1d; color: #fecaca; }
  .b-strong-down  { background: #7f1d1d; color: #fee2e2; }
  details > summary { list-style: none; cursor: pointer; user-select: none; }
  details > summary::-webkit-details-marker { display: none; }
  details > summary::after { content: ' ▾'; color: #71717a; transition: transform 0.2s; display: inline-block; }
  details[open] > summary::after { transform: rotate(180deg); }
  .gauge-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .gauge-on  { background: currentColor; }
  .gauge-off { background: #3f3f46; }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #18181b; }
  ::-webkit-scrollbar-thumb { background: #52525b; border-radius: 3px; }
  .chart-container { background: #0a0a0a; border-radius: 8px; }
</style>
<script>tailwind.config = { darkMode: 'class' };</script>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen antialiased">

<header class="sticky top-0 z-30 backdrop-blur bg-zinc-950/80 border-b border-zinc-800">
  <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="text-2xl">📊</div>
      <div>
        <h1 class="font-bold text-lg leading-tight">StockWatch</h1>
        <p class="text-xs text-zinc-400">__COUNT__개 카드 · __GEN_TIME__ 갱신</p>
      </div>
    </div>
  </div>
</header>

<div class="max-w-7xl mx-auto px-4 py-3 border-b border-zinc-800">
  <div class="flex flex-wrap gap-2">
    <input id="search" type="text" placeholder="🔍 종목 검색"
      class="flex-1 min-w-[180px] bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm placeholder-zinc-500 focus:outline-none focus:border-blue-500" />
    <select id="market" class="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm">
      <option value="">🌍 전체</option>
      <option value="KR">🇰🇷 KR</option><option value="US">🇺🇸 US</option>
      <option value="JP">🇯🇵 JP</option><option value="UK">🇬🇧 UK</option><option value="DE">🇩🇪 DE</option>
    </select>
    <select id="sort" class="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm">
      <option value="date">📅 최신</option>
      <option value="net">💪 강도</option>
      <option value="risk">⚠️ 안전</option>
    </select>
  </div>
</div>

<div id="stats" class="max-w-7xl mx-auto px-4 py-2 text-xs text-zinc-500"></div>

<main class="max-w-7xl mx-auto px-4 py-4">
  <div id="grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"></div>
</main>

<div id="modal" class="fixed inset-0 bg-black/85 z-50 hidden overflow-y-auto" onclick="if(event.target.id==='modal')closeModal()">
  <div class="min-h-screen p-3 flex items-start">
    <div class="bg-zinc-900 rounded-xl max-w-4xl w-full mx-auto my-4 p-4" id="modal-content"></div>
  </div>
</div>

<footer class="max-w-7xl mx-auto px-4 py-8 text-center text-xs text-zinc-600">
  StockWatch · 정보 제공 목적 · 투자 권유 아님
</footer>

<script>
const CARDS = __CARDS_DATA__;
const PRICES = __PRICES_DATA__;
const FLAG = { KR: '🇰🇷', US: '🇺🇸', JP: '🇯🇵', UK: '🇬🇧', DE: '🇩🇪' };

function vClass(v) {
  if (!v) return 'v-mixed';
  if (v.includes('강한 상승')) return 'v-strong-up';
  if (v.includes('상승 우위')) return 'v-up';
  if (v.includes('약한 상승')) return 'v-weak-up';
  if (v.includes('강한 하락')) return 'v-strong-down';
  if (v.includes('하락 우위')) return 'v-down';
  if (v.includes('약한 하락')) return 'v-weak-down';
  return 'v-mixed';
}
function bClass(v) { return vClass(v).replace('v-', 'b-'); }
function fmtPrice(p, c) {
  if (p == null) return '-';
  if (p > 1000) return Math.round(p).toLocaleString() + ' ' + (c||'');
  return p.toFixed(2) + ' ' + (c||'');
}

// SVG 스파크라인 (60일 가격 미니 차트)
function sparkline(prices, color) {
  if (!prices || prices.length < 2) return '';
  const data = prices.slice(-60).map(p => p.close);
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const w = 100, h = 32;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const last = data[data.length - 1], first = data[0];
  const trendColor = last > first ? '#10b981' : last < first ? '#ef4444' : '#facc15';
  const c = color || trendColor;
  return `<svg viewBox="0 0 ${w} ${h}" class="w-full h-8" preserveAspectRatio="none">
    <polyline points="${points}" fill="none" stroke="${c}" stroke-width="1.5" stroke-linejoin="round" />
  </svg>`;
}

// 점수 가로 스택 바 (↑↓△)
function scoreBar(scores) {
  const total = scores.up + scores.down + scores.neut || 1;
  const upPct = (scores.up / total) * 100;
  const downPct = (scores.down / total) * 100;
  const neutPct = (scores.neut / total) * 100;
  return `<div class="flex h-2 rounded-full overflow-hidden bg-zinc-800">
    <div class="bg-emerald-500" style="width:${upPct}%"></div>
    <div class="bg-red-500" style="width:${downPct}%"></div>
    <div class="bg-yellow-500" style="width:${neutPct}%"></div>
  </div>`;
}

// 리스크 게이지 (10개 점, 채워진 정도)
function riskGauge(score) {
  const filled = Math.min(10, Math.round(score / 10));
  const color = score >= 70 ? 'text-red-500' : score >= 50 ? 'text-orange-500' : score >= 30 ? 'text-yellow-500' : 'text-emerald-500';
  let dots = '';
  for (let i = 0; i < 10; i++) {
    dots += `<span class="gauge-dot ${i < filled ? 'gauge-on ' + color : 'gauge-off'}"></span>`;
  }
  return `<div class="flex items-center gap-0.5 ${color}">${dots}</div>`;
}

function render() {
  const search = document.getElementById('search').value.trim().toLowerCase();
  const market = document.getElementById('market').value;
  const sort = document.getElementById('sort').value;
  let f = CARDS.filter(c => {
    if (search && !(c.name||'').toLowerCase().includes(search) && !(c.symbol||'').toLowerCase().includes(search)) return false;
    if (market && c.market !== market) return false;
    return true;
  });
  if (sort === 'date') f.sort((a,b) => (b.date||'').localeCompare(a.date||''));
  else if (sort === 'net') f.sort((a,b) => (b.scores.up-b.scores.down) - (a.scores.up-a.scores.down));
  else if (sort === 'risk') f.sort((a,b) => (a.risk_score||0) - (b.risk_score||0));
  document.getElementById('grid').innerHTML = f.map(renderCard).join('');
  document.getElementById('stats').textContent = `${f.length} / ${CARDS.length}건`;
}

function renderCard(c) {
  const flag = FLAG[c.market] || '';
  const net = c.scores.up - c.scores.down;
  const symKey = `${c.symbol}_${c.market}`;
  const prices = PRICES[symKey] || [];
  const last = prices[prices.length - 1];
  const dayChange = last && prices.length >= 2 ?
    ((last.close / prices[prices.length-2].close - 1) * 100) : null;

  return `<div onclick="openCard(${c.id})" class="stock-card cursor-pointer block bg-zinc-900 ${vClass(c.verdict)} rounded-lg p-3.5 hover:bg-zinc-800/80">
    <div class="flex items-start justify-between gap-2 mb-1">
      <div class="flex-1 min-w-0">
        <div class="text-[10px] text-zinc-500">${flag} ${c.market} · ${c.sector||'-'}</div>
        <div class="font-semibold text-sm truncate" title="${c.name}">${c.name}</div>
        <div class="text-[10px] font-mono text-zinc-500">${c.symbol}</div>
      </div>
      <div class="text-right">
        <div class="text-base font-bold whitespace-nowrap">${fmtPrice(c.issue_price, c.currency)}</div>
        ${dayChange != null ? `<div class="text-[10px] ${dayChange >= 0 ? 'text-emerald-400' : 'text-red-400'}">${dayChange >= 0 ? '+' : ''}${dayChange.toFixed(2)}%</div>` : ''}
      </div>
    </div>

    ${prices.length ? `<div class="my-2">${sparkline(prices)}</div>` : '<div class="my-2 h-8 flex items-center text-[10px] text-zinc-600">차트 데이터 없음</div>'}

    <div class="flex items-center gap-2 flex-wrap mt-2">
      <span class="px-2 py-0.5 rounded-full text-[11px] ${bClass(c.verdict)} font-medium">${c.verdict_emoji} ${c.verdict}</span>
    </div>

    <div class="mt-2.5">
      ${scoreBar(c.scores)}
      <div class="flex justify-between mt-1 text-[10px] font-mono">
        <span class="text-emerald-400">↑${c.scores.up}</span>
        <span class="text-yellow-400">△${c.scores.neut}</span>
        <span class="text-red-400">↓${c.scores.down}</span>
        <span class="text-zinc-400">net ${net>=0?'+':''}${net}</span>
      </div>
    </div>

    <div class="mt-2 flex items-center justify-between gap-2">
      <span class="text-[10px] text-zinc-500">리스크</span>
      ${riskGauge(c.risk_score)}
      <span class="text-[10px] text-zinc-400 font-mono">${c.risk_score}</span>
    </div>

    ${c.summary ? `<div class="mt-2 text-[11px] text-zinc-300 italic border-t border-zinc-800 pt-2">💡 ${c.summary.length>50?c.summary.slice(0,50)+'…':c.summary}</div>` : ''}
  </div>`;
}

let activeCharts = [];

function openCard(id) {
  const c = CARDS.find(x => x.id === id);
  if (!c) return;
  document.getElementById('modal-content').innerHTML = renderModal(c);
  document.getElementById('modal').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  setTimeout(() => initCharts(c), 50);
}
function closeModal() {
  activeCharts.forEach(ch => { try { ch.remove?.() ?? ch.destroy?.(); } catch(e){} });
  activeCharts = [];
  document.getElementById('modal').classList.add('hidden');
  document.body.style.overflow = '';
}

function renderModal(c) {
  const flag = FLAG[c.market] || '';
  const net = c.scores.up - c.scores.down;
  return `
    <div class="flex justify-between mb-3">
      <button onclick="closeModal()" class="text-zinc-400 hover:text-zinc-100 text-sm">← 닫기</button>
      <span class="text-xs text-zinc-500">#${c.id}</span>
    </div>

    <!-- 헤더 -->
    <div class="${vClass(c.verdict)} pl-3 mb-4">
      <div class="text-xs text-zinc-500 mb-1">${flag} ${c.market} · ${c.sector||'-'} · ${c.date}</div>
      <h2 class="text-2xl font-bold">${c.name}</h2>
      <div class="text-sm font-mono text-zinc-400 mt-1">${c.symbol}</div>
      <div class="flex items-baseline gap-3 mt-2">
        <span class="text-2xl font-bold">${fmtPrice(c.issue_price, c.currency)}</span>
        <span class="px-2.5 py-1 rounded-full text-xs ${bClass(c.verdict)} font-semibold">${c.verdict_emoji} ${c.verdict}</span>
      </div>
    </div>

    ${c.summary ? `<div class="bg-zinc-800/50 rounded-lg p-3 italic mb-4 border-l-2 border-blue-500">💡 ${c.summary}</div>` : ''}

    <!-- 캔들차트 -->
    <div class="mb-4">
      <div class="text-xs text-zinc-500 mb-1">📈 가격 추이 (180일)</div>
      <div id="candle-chart" class="chart-container" style="height: 280px;"></div>
    </div>

    <!-- 시그널 레이더 + 종합 게이지 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
      <div class="md:col-span-2 bg-zinc-800/30 rounded-lg p-3">
        <div class="text-xs text-zinc-500 mb-2">📊 10시그널 강도 비교</div>
        <div style="height: 280px;"><canvas id="radar-chart"></canvas></div>
      </div>
      <div class="bg-zinc-800/30 rounded-lg p-3 flex flex-col">
        <div class="text-xs text-zinc-500 mb-2">⚙️ 종합</div>
        <div class="text-3xl font-bold text-center mt-2">${c.verdict_emoji}</div>
        <div class="text-center text-sm font-medium">${c.verdict}</div>
        <div class="mt-3">${scoreBar(c.scores)}</div>
        <div class="flex justify-between mt-1 text-xs font-mono">
          <span class="text-emerald-400">↑${c.scores.up}</span>
          <span class="text-yellow-400">△${c.scores.neut}</span>
          <span class="text-red-400">↓${c.scores.down}</span>
        </div>
        <div class="mt-4 text-xs text-zinc-500">⚠️ 리스크</div>
        <div class="flex items-center justify-between mt-1">
          ${riskGauge(c.risk_score)}
          <span class="text-sm font-mono">${c.risk_score}/100</span>
        </div>
        <div class="text-[10px] text-zinc-500 text-right">${c.risk_level}</div>
      </div>
    </div>

    <!-- 강점/약점 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
      ${renderSW('✨ 강점', c.strengths, 'up')}
      ${renderSW('⚠️ 약점', c.weaknesses, 'down')}
    </div>

    ${c.risk_factors.length ? `<div class="bg-red-950/30 border border-red-900/50 rounded p-3 mb-4">
      <div class="text-sm font-semibold text-red-300 mb-2">⚠️ 리스크 요인</div>
      <ul class="text-sm text-red-100 space-y-1">${c.risk_factors.map(f => `<li>• ${f}</li>`).join('')}</ul></div>` : ''}

    <!-- 시그널 상세 (모두 토글) -->
    <div class="text-xs text-zinc-500 mb-2">▾ 시그널별 세부 체크 (탭하여 펼치기)</div>
    ${renderSignalGroups(c)}
  `;
}

function renderSignalGroups(c) {
  const groups = [
    ['🤖 AI 분석', ['팩트헌터', 'Why 엔진', '글로벌 팩트헌터']],
    ['📈 기술 분석', ['차트 시그널', '차트 패턴', '돌파 차트']],
    ['💰 수급·퀀트', ['머니플로우', '퀀트 팩터']],
    ['📊 펀더멘털·이벤트', ['재무 분석', '이벤트 추적']],
  ];
  return groups.map(([title, types]) => {
    const sigs = c.signals.filter(s => types.includes(s.signal_type));
    if (!sigs.length) return '';
    return `<details class="bg-zinc-800/30 rounded p-3 mb-2">
      <summary class="text-sm font-semibold flex justify-between">
        <span>${title}</span>
        <span class="text-xs text-zinc-400 font-mono">
          ↑${sigs.reduce((a,s)=>a+s.score_up,0)} ↓${sigs.reduce((a,s)=>a+s.score_down,0)}
        </span>
      </summary>
      <div class="mt-3 space-y-2">${sigs.map(renderSig).join('')}</div></details>`;
  }).join('');
}

function renderSig(s) {
  const checks = (s.details||{}).checks || [];
  return `<details class="bg-zinc-900 rounded p-2.5">
    <summary class="flex items-center justify-between text-sm">
      <div class="flex items-center gap-2 flex-1 min-w-0">
        <span class="font-medium truncate">${s.signal_type}</span>
        ${miniBar(s.score_up, s.score_down, s.score_neut)}
      </div>
      <span class="font-mono text-xs ml-2">
        <span class="text-emerald-400">↑${s.score_up}</span>
        <span class="text-red-400 ml-1">↓${s.score_down}</span>
      </span>
    </summary>
    <div class="mt-2 pt-2 border-t border-zinc-700/50">
      <div class="text-xs italic text-zinc-300 mb-2">${s.summary||''}</div>
      ${checks.length ? `<ul class="space-y-1 text-xs">${checks.map(c => `<li class="flex gap-2"><span class="${c.verdict==='↑'?'text-emerald-400':c.verdict==='↓'?'text-red-400':'text-yellow-400'} font-bold w-3">${c.verdict}</span><span class="text-zinc-300 min-w-[80px]">${c.name}</span><span class="text-zinc-500 flex-1">${c.reason}</span></li>`).join('')}</ul>` : '<p class="text-xs text-zinc-500">상세 없음</p>'}
    </div></details>`;
}

function miniBar(up, down, neut) {
  const total = up + down + neut || 1;
  return `<div class="flex h-1.5 w-16 rounded-full overflow-hidden bg-zinc-800">
    <div class="bg-emerald-500" style="width:${up/total*100}%"></div>
    <div class="bg-red-500" style="width:${down/total*100}%"></div>
    <div class="bg-yellow-500" style="width:${neut/total*100}%"></div>
  </div>`;
}

function renderSW(title, items, kind) {
  if (!items.length) return `<div class="bg-zinc-800/40 rounded p-3"><div class="text-sm font-semibold mb-2">${title}</div><p class="text-xs text-zinc-500">없음</p></div>`;
  const arrow = kind === 'up' ? '↑' : '↓';
  const color = kind === 'up' ? 'text-emerald-400' : 'text-red-400';
  return `<div class="bg-zinc-800/40 rounded p-3"><div class="text-sm font-semibold mb-2">${title}</div>
    <ul class="space-y-2">${items.slice(0,5).map(i => `<li class="text-xs"><div class="flex items-start gap-1.5"><span class="${color} font-bold mt-0.5">${arrow}</span><div class="flex-1"><div class="text-zinc-200 font-medium">${i.name}</div><div class="text-zinc-500 text-[10px]">${i.reason}</div><div class="text-zinc-600 text-[10px]">[${i.signal}]</div></div></div></li>`).join('')}</ul></div>`;
}

function initCharts(c) {
  // 캔들차트
  const symKey = `${c.symbol}_${c.market}`;
  const prices = PRICES[symKey];
  const candleEl = document.getElementById('candle-chart');
  if (candleEl && prices && prices.length > 0) {
    const chart = LightweightCharts.createChart(candleEl, {
      layout: { background: { color: '#0a0a0a' }, textColor: '#a1a1aa' },
      grid: { vertLines: { color: '#1f1f23' }, horzLines: { color: '#1f1f23' } },
      width: candleEl.clientWidth,
      height: 280,
      timeScale: { borderColor: '#3f3f46', timeVisible: false },
      rightPriceScale: { borderColor: '#3f3f46' },
    });
    const candle = chart.addCandlestickSeries({
      upColor: '#10b981', downColor: '#ef4444',
      borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });
    candle.setData(prices.map(p => ({
      time: p.time, open: p.open, high: p.high, low: p.low, close: p.close
    })));
    const vol = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      color: '#52525b',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    vol.setData(prices.map(p => ({
      time: p.time,
      value: p.volume,
      color: p.close >= p.open ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'
    })));
    chart.timeScale().fitContent();
    activeCharts.push(chart);
    window.addEventListener('resize', () => chart.applyOptions({ width: candleEl.clientWidth }));
  } else if (candleEl) {
    candleEl.innerHTML = '<div class="h-full flex items-center justify-center text-zinc-500 text-sm">📊 차트 데이터 없음 (워치리스트 종목만 차트 제공)</div>';
  }

  // 레이더차트
  const radarEl = document.getElementById('radar-chart');
  if (radarEl && c.signals.length) {
    const labels = c.signals.map(s => s.signal_type);
    // 점수: net = (up - down) / total, -1~1을 0~100으로 변환
    const scores = c.signals.map(s => {
      const total = s.score_up + s.score_down + s.score_neut || 1;
      return Math.round(((s.score_up - s.score_down) / total + 1) * 50);  // 0~100
    });
    const upStr = c.signals.map(s => {
      const total = s.score_up + s.score_down + s.score_neut || 1;
      return Math.round((s.score_up / total) * 100);
    });
    const downStr = c.signals.map(s => {
      const total = s.score_up + s.score_down + s.score_neut || 1;
      return Math.round((s.score_down / total) * 100);
    });

    const chart = new Chart(radarEl, {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [
          {
            label: '↑ 강도',
            data: upStr,
            backgroundColor: 'rgba(16,185,129,0.18)',
            borderColor: 'rgba(16,185,129,0.9)',
            borderWidth: 2,
            pointBackgroundColor: '#10b981',
            pointRadius: 3,
          },
          {
            label: '↓ 강도',
            data: downStr,
            backgroundColor: 'rgba(239,68,68,0.18)',
            borderColor: 'rgba(239,68,68,0.9)',
            borderWidth: 2,
            pointBackgroundColor: '#ef4444',
            pointRadius: 3,
          },
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            min: 0, max: 100,
            ticks: { color: '#52525b', backdropColor: 'transparent', stepSize: 25, font: { size: 9 } },
            grid: { color: '#27272a' },
            angleLines: { color: '#27272a' },
            pointLabels: { color: '#a1a1aa', font: { size: 10 } }
          }
        },
        plugins: {
          legend: { labels: { color: '#a1a1aa', font: { size: 11 }, boxWidth: 12 }, position: 'bottom' },
          tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.r}%` } }
        }
      }
    });
    activeCharts.push(chart);
  }
}

['search','market','sort'].forEach(id => {
  document.getElementById(id).addEventListener('input', render);
  document.getElementById(id).addEventListener('change', render);
});
render();

// ESC로 모달 닫기
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
