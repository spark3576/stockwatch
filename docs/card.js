// card.html — 분석 카드 상세 페이지

async function loadCardDetail() {
  const url = new URL(location.href);
  const id = url.searchParams.get('id');
  const target = document.getElementById('card-detail');
  const cardIdSpan = document.getElementById('card-id');

  if (!id) {
    target.innerHTML = '<div class="text-center py-16 text-red-400">id 파라미터 없음</div>';
    return;
  }
  cardIdSpan.textContent = `#${id}`;

  let card;
  try {
    card = await fetch(`data/cards/${id}.json`).then(r => r.json());
  } catch (e) {
    target.innerHTML = '<div class="text-center py-16 text-red-400">카드 데이터 로드 실패</div>';
    return;
  }

  document.title = `${card.name} (${card.symbol}) — StockWatch`;
  target.innerHTML = renderDetail(card);
}

function renderDetail(c) {
  const flag = FLAG[c.market] || '';
  const vClass = verdictClass(c.verdict);
  const bClass = badgeClass(c.verdict);
  const rClass = riskBadgeClass(c.risk_level);
  const net = c.scores.up - c.scores.down;

  // 시그널 그룹 분류
  const aiSignals = (c.signals || []).filter(s =>
    ['팩트헌터', 'Why 엔진', '글로벌 팩트헌터'].includes(s.signal_type)
  );
  const techSignals = (c.signals || []).filter(s =>
    ['차트 시그널', '차트 패턴', '돌파 차트'].includes(s.signal_type)
  );
  const flowSignals = (c.signals || []).filter(s =>
    ['머니플로우', '퀀트 팩터'].includes(s.signal_type)
  );
  const fundSignals = (c.signals || []).filter(s =>
    ['재무 분석', '이벤트 추적'].includes(s.signal_type)
  );

  return `
    <!-- 메인 카드 -->
    <div class="bg-zinc-900 ${vClass} rounded-xl p-5 mb-4">
      <div class="flex items-start justify-between gap-3 mb-3">
        <div class="flex-1 min-w-0">
          <div class="text-xs text-zinc-500 mb-1">${flag} ${c.market} · ${c.sector || '-'} · ${formatDate(c.date || c.issued_at)}</div>
          <h1 class="text-2xl font-bold leading-tight">${c.name}</h1>
          <div class="text-sm font-mono text-zinc-400 mt-1">${c.symbol}</div>
        </div>
        <div class="text-right">
          <div class="text-2xl font-bold whitespace-nowrap">${formatPrice(c.issue_price, c.currency)}</div>
        </div>
      </div>

      <div class="flex items-center gap-2 flex-wrap mb-3">
        <span class="px-3 py-1.5 rounded-full text-sm ${bClass} font-semibold">
          ${verdictEmoji(c.verdict)} ${c.verdict}
        </span>
        <span class="px-3 py-1.5 rounded-full text-sm ${rClass}">
          ⚠️ 리스크 ${c.risk_level} (${c.risk_score}/100)
        </span>
        <span class="px-3 py-1.5 rounded-full text-sm bg-zinc-800 text-zinc-300 font-mono">
          <span class="text-emerald-400">↑${c.scores.up}</span>
          <span class="text-red-400 ml-1.5">↓${c.scores.down}</span>
          <span class="text-yellow-400 ml-1.5">△${c.scores.neut}</span>
          <span class="ml-2 text-zinc-400">net ${net >= 0 ? '+' : ''}${net}</span>
        </span>
      </div>

      ${c.summary ? `
      <div class="bg-zinc-800/50 rounded-lg p-3 text-zinc-200 italic border-l-2 border-blue-500">
        💡 ${c.summary}
      </div>` : ''}
    </div>

    <!-- 강점/약점 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
      ${renderStrengthsWeaknesses('✨ 핵심 강점', c.strengths || [], 'up')}
      ${renderStrengthsWeaknesses('⚠️ 주의 신호', c.weaknesses || [], 'down')}
    </div>

    ${(c.risk_factors && c.risk_factors.length) ? `
    <div class="bg-red-950/30 border border-red-900/50 rounded-lg p-4 mb-4">
      <h3 class="text-sm font-semibold text-red-300 mb-2">⚠️ 리스크 요인</h3>
      <ul class="text-sm text-red-100 space-y-1">
        ${c.risk_factors.map(f => `<li>• ${f}</li>`).join('')}
      </ul>
    </div>` : ''}

    <!-- 시그널 그룹들 -->
    ${renderSignalGroup('🤖 AI 분석', aiSignals)}
    ${renderSignalGroup('📈 기술 분석', techSignals)}
    ${renderSignalGroup('💰 수급·퀀트', flowSignals)}
    ${renderSignalGroup('📊 펀더멘털·이벤트', fundSignals)}
  `;
}

function renderStrengthsWeaknesses(title, items, kind) {
  if (!items.length) {
    return `
      <div class="bg-zinc-900 rounded-lg p-4">
        <h3 class="text-sm font-semibold mb-2">${title}</h3>
        <p class="text-sm text-zinc-500">없음</p>
      </div>
    `;
  }
  const arrow = kind === 'up' ? '↑' : '↓';
  const color = kind === 'up' ? 'verdict-up-text' : 'verdict-down-text';
  return `
    <div class="bg-zinc-900 rounded-lg p-4">
      <h3 class="text-sm font-semibold mb-3">${title}</h3>
      <ul class="space-y-2">
        ${items.map(i => `
          <li class="text-sm">
            <div class="flex items-start gap-2">
              <span class="${color} font-bold mt-0.5">${arrow}</span>
              <div class="flex-1 min-w-0">
                <div class="text-zinc-200">${i.name}</div>
                <div class="text-xs text-zinc-400 mt-0.5">${i.reason}</div>
                <div class="text-xs text-zinc-600 mt-0.5">[${i.signal}]</div>
              </div>
            </div>
          </li>
        `).join('')}
      </ul>
    </div>
  `;
}

function renderSignalGroup(title, signals) {
  if (!signals.length) return '';

  return `
    <div class="bg-zinc-900 rounded-lg p-4 mb-3">
      <h3 class="text-sm font-semibold mb-3">${title}</h3>
      <div class="space-y-2">
        ${signals.map(renderSignalRow).join('')}
      </div>
    </div>
  `;
}

function renderSignalRow(s) {
  const checks = (s.details || {}).checks || [];
  const total = s.score_up + s.score_down + s.score_neut || 1;
  return `
    <details class="bg-zinc-800/50 rounded p-3">
      <summary class="flex items-center justify-between gap-2">
        <span class="font-medium">${s.signal_type}</span>
        <span class="font-mono text-xs">
          <span class="text-emerald-400">↑${s.score_up}</span>
          <span class="text-red-400 ml-1.5">↓${s.score_down}</span>
          <span class="text-yellow-400 ml-1.5">△${s.score_neut}</span>
        </span>
      </summary>
      <div class="mt-2 pt-2 border-t border-zinc-700/50">
        <div class="text-xs text-zinc-300 italic mb-2">${s.summary || ''}</div>
        ${checks.length ? `
        <ul class="space-y-1 text-xs">
          ${checks.map(c => `
            <li class="flex items-start gap-2">
              <span class="${c.verdict === '↑' ? 'verdict-up-text' : c.verdict === '↓' ? 'verdict-down-text' : 'verdict-neut-text'} font-bold">${c.verdict}</span>
              <span class="text-zinc-300 font-medium min-w-[100px]">${c.name}</span>
              <span class="text-zinc-500 flex-1">${c.reason}</span>
            </li>
          `).join('')}
        </ul>` : '<p class="text-xs text-zinc-500">상세 데이터 없음</p>'}
      </div>
    </details>
  `;
}

// 진입점
if (document.getElementById('card-detail')) {
  loadCardDetail();
}
