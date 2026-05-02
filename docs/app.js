// StockWatch 대시보드 — 메인 로직 (vanilla JS)

const FLAG = { KR: '🇰🇷', US: '🇺🇸', JP: '🇯🇵', UK: '🇬🇧', DE: '🇩🇪' };

// 판정 → CSS 클래스
function verdictClass(v) {
  if (!v) return 'verdict-mixed';
  if (v.includes('강한 상승')) return 'verdict-strong-up';
  if (v.includes('상승 우위')) return 'verdict-up';
  if (v.includes('약한 상승')) return 'verdict-weak-up';
  if (v.includes('강한 하락')) return 'verdict-strong-down';
  if (v.includes('하락 우위')) return 'verdict-down';
  if (v.includes('약한 하락')) return 'verdict-weak-down';
  return 'verdict-mixed';
}
function badgeClass(v) {
  return verdictClass(v).replace('verdict-', 'badge-');
}
function riskBadgeClass(level) {
  if (!level) return 'badge-risk-mid';
  if (level.includes('낮음')) return 'badge-risk-low';
  if (level.includes('매우 높음')) return 'badge-risk-extreme';
  if (level.includes('높음')) return 'badge-risk-high';
  return 'badge-risk-mid';
}
function verdictEmoji(v) {
  if (!v) return '🟡';
  if (v.includes('강한 상승')) return '🟢🟢';
  if (v.includes('상승')) return '🟢';
  if (v.includes('강한 하락')) return '🔴🔴';
  if (v.includes('하락')) return '🔴';
  return '🟡';
}

function formatPrice(price, currency) {
  if (price == null) return '-';
  if (price > 1000) return Math.round(price).toLocaleString() + ' ' + (currency || '');
  return price.toFixed(2) + ' ' + (currency || '');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = dateStr.split(' ')[0].split('T')[0];
  return d;
}

// 카드 그리드 렌더링 (index.html)
async function loadCardGrid() {
  const grid = document.getElementById('card-grid');
  const meta = document.getElementById('meta-info');
  const stats = document.getElementById('stats-bar');
  const empty = document.getElementById('empty-state');

  let manifest = {};
  try {
    manifest = await fetch('data/manifest.json').then(r => r.json());
  } catch (e) { /* ignore */ }

  let cards = [];
  try {
    cards = await fetch('data/cards.json').then(r => r.json());
  } catch (e) {
    grid.innerHTML = '<div class="col-span-full text-center py-16 text-red-400">데이터 로드 실패. python scripts/export_dashboard.py 를 먼저 실행하세요.</div>';
    return;
  }

  if (manifest.generated_at) {
    const dt = new Date(manifest.generated_at);
    meta.textContent = `${cards.length}개 카드 · ${dt.toLocaleString('ko-KR', { dateStyle: 'short', timeStyle: 'short' })} 갱신`;
  }

  // 필터 + 정렬 적용
  const apply = () => {
    const search = document.getElementById('search-input').value.trim().toLowerCase();
    const market = document.getElementById('market-filter').value;
    const verdict = document.getElementById('verdict-filter').value;
    const sortBy = document.getElementById('sort-by').value;

    let filtered = cards.filter(c => {
      if (search && !(c.name || '').toLowerCase().includes(search) &&
          !(c.symbol || '').toLowerCase().includes(search)) return false;
      if (market && c.market !== market) return false;
      if (verdict) {
        if (verdict === '상승' && !c.verdict.includes('상승')) return false;
        if (verdict === '하락' && !c.verdict.includes('하락')) return false;
        if (verdict === '강한 상승' && !c.verdict.includes('강한 상승')) return false;
        if (verdict === '강한 하락' && !c.verdict.includes('강한 하락')) return false;
        if (verdict === '혼조' && !c.verdict.includes('혼조')) return false;
      }
      return true;
    });

    if (sortBy === 'date') {
      filtered.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    } else if (sortBy === 'net') {
      filtered.sort((a, b) => (b.scores.up - b.scores.down) - (a.scores.up - a.scores.down));
    } else if (sortBy === 'risk') {
      filtered.sort((a, b) => (a.risk_score || 0) - (b.risk_score || 0));
    }

    grid.innerHTML = filtered.map(renderCard).join('');
    empty.classList.toggle('hidden', filtered.length > 0);
    stats.textContent = `${filtered.length} / ${cards.length}건 표시`;
  };

  apply();
  ['search-input', 'market-filter', 'verdict-filter', 'sort-by'].forEach(id => {
    const el = document.getElementById(id);
    el.addEventListener('input', apply);
    el.addEventListener('change', apply);
  });

  document.getElementById('refresh-btn').addEventListener('click', () => location.reload());
}

function renderCard(c) {
  const flag = FLAG[c.market] || '';
  const vClass = verdictClass(c.verdict);
  const bClass = badgeClass(c.verdict);
  const rClass = riskBadgeClass(c.risk_level);
  const net = c.scores.up - c.scores.down;
  const oneliner = c.ai_summary || c.summary || '';
  const truncated = oneliner.length > 60 ? oneliner.slice(0, 60) + '…' : oneliner;

  return `
    <a href="card.html?id=${c.id}" class="stock-card block bg-zinc-900 ${vClass} rounded-lg p-4 hover:bg-zinc-800/80">
      <div class="flex items-start justify-between gap-2 mb-2">
        <div class="flex-1 min-w-0">
          <div class="text-xs text-zinc-500 mb-0.5">${flag} ${c.market} · ${c.sector || '-'}</div>
          <div class="font-semibold text-zinc-100 truncate" title="${c.name}">${c.name}</div>
          <div class="text-xs font-mono text-zinc-400">${c.symbol}</div>
        </div>
        <div class="text-right">
          <div class="text-zinc-200 font-semibold whitespace-nowrap">${formatPrice(c.issue_price, c.currency)}</div>
          <div class="text-xs text-zinc-500">${formatDate(c.date || c.issued_at)}</div>
        </div>
      </div>

      <div class="flex items-center gap-2 mt-3 flex-wrap">
        <span class="px-2 py-1 rounded text-xs ${bClass} font-medium">
          ${verdictEmoji(c.verdict)} ${c.verdict}
        </span>
        <span class="px-2 py-1 rounded text-xs ${rClass}">
          리스크 ${c.risk_score}/100
        </span>
      </div>

      <div class="mt-3 flex items-center justify-between text-sm">
        <div class="font-mono">
          <span class="text-emerald-400">↑${c.scores.up}</span>
          <span class="text-red-400 ml-2">↓${c.scores.down}</span>
          <span class="text-yellow-400 ml-2">△${c.scores.neut}</span>
        </div>
        <div class="text-xs text-zinc-400">
          ${net >= 0 ? '+' : ''}${net} 종합
        </div>
      </div>

      ${oneliner ? `
      <div class="mt-3 text-sm text-zinc-300 italic border-t border-zinc-800 pt-2">
        💡 ${truncated}
      </div>` : ''}
    </a>
  `;
}

// 진입점 — index.html 로드 시
if (document.getElementById('card-grid')) {
  loadCardGrid();
}
