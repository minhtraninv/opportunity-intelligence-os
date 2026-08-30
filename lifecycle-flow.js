(() => {
  const esc = (value) => String(value ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');

  const labels = {
    learning_history: 'LEARNING HISTORY',
    strengthening: 'STRENGTHENING',
    stable: 'STABLE',
    weakening: 'WEAKENING',
    reversal_watch: 'REVERSAL WATCH',
  };

  const arrow = (x) => ({
    strengthening: '↑',
    stable: '→',
    weakening: '↓',
    reversal_watch: '↘',
    new: '•',
  })[x] || '•';

  function ensure(){
    const anchor = document.getElementById('contradictionGrid') || document.getElementById('moneyFlowSummary');
    if(!anchor) return null;
    let grid = document.getElementById('lifecycleGrid');
    if(grid) return grid;
    anchor.insertAdjacentHTML('afterend', `
      <div id="lifecycleHead" class="section-head" style="margin-top:24px">
        <div>
          <div class="eyebrow">THESIS LIFECYCLE · V2.4</div>
          <h2>Thesis đang mạnh lên, đứng yên hay mất lực?</h2>
        </div>
        <span id="lifecycleStatus" class="muted">Đang đọc lịch sử…</span>
      </div>
      <div id="lifecycleSummary" class="panel" style="margin-bottom:14px"></div>
      <div id="lifecycleGrid" class="signal-grid" style="margin-bottom:22px"></div>`);
    return document.getElementById('lifecycleGrid');
  }

  function signed(value){
    if(value === null || value === undefined) return '—';
    const n = Number(value);
    return Number.isFinite(n) ? `${n > 0 ? '+' : ''}${n}` : '—';
  }

  function card(row){
    const state = row.lifecycle_state || 'learning_history';
    const provisional = row.provisional_direction || 'new';
    const downgrade = (row.downgrade_conditions || []).slice(0,3).map(x => `<li>${esc(x)}</li>`).join('');
    return `<article class="signal-card">
      <div class="signal-top">
        <div>
          <div class="eyebrow">${esc(labels[state] || state.toUpperCase())}</div>
          <div class="signal-title">${esc(row.theme_label || row.theme_id)}</div>
          <div class="signal-meta">
            <span class="pill">${esc(row.observation_days)} ngày</span>
            <span class="pill">${esc(row.snapshot_count)} snapshots</span>
            <span class="pill">confidence: ${esc(row.history_confidence)}</span>
          </div>
        </div>
        <div class="signal-score ${Number(row.current_adjusted_score) >= 70 ? 'hot' : ''}">${esc(row.current_adjusted_score)}</div>
      </div>

      <div style="margin-top:10px;font-weight:800;font-size:1.05rem">
        ${esc(arrow(provisional))} ${esc(provisional.toUpperCase())}
        <span class="muted small"> · Δ previous ${esc(signed(row.delta_vs_previous))}</span>
      </div>
      <div class="muted small" style="margin-top:6px">${esc(row.reason || '')}</div>

      <div class="signal-meta" style="margin-top:10px">
        <span class="pill">Raw ${esc(row.current_score)}</span>
        <span class="pill">After tension ${esc(row.current_adjusted_score)}</span>
        <span class="pill">7d Δ ${esc(signed(row.delta_vs_7d))}</span>
        <span class="pill">${esc(row.supply_gap_status || 'supply unknown')}</span>
      </div>

      ${downgrade ? `<details style="margin-top:12px"><summary style="cursor:pointer;font-weight:800">Điều gì sẽ làm thesis yếu đi?</summary><ul class="plain-list" style="margin-top:8px">${downgrade}</ul></details>` : ''}
    </article>`;
  }

  fetch('data/thesis_lifecycle.json', {cache:'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if(!data) return;
      const grid = ensure();
      if(!grid) return;
      const c = data.coverage || {};
      const status = document.getElementById('lifecycleStatus');
      const summary = document.getElementById('lifecycleSummary');
      if(status) status.textContent = `${c.max_observation_days ?? 0} ngày · ${c.history_snapshots ?? 0} snapshots · ${c.directional_lifecycle_active ? 'LIFECYCLE ACTIVE' : 'LEARNING HISTORY'}`;
      if(summary) summary.innerHTML = `
        <div class="eyebrow">DELTA THESIS</div>
        <div class="thesis-text" style="margin-top:7px">${esc(data.thesis || '—')}</div>
        <div class="muted small" style="margin-top:8px">Chỉ sau ≥3 ngày quan sát hệ thống mới được phép gọi strengthening / weakening / reversal. Trước đó mọi hướng chỉ là provisional.</div>`;
      const rows = data.themes || [];
      grid.innerHTML = rows.length ? rows.map(card).join('') : '<div class="panel muted">Chưa có lịch sử thesis.</div>';
    })
    .catch(() => {});
})();
