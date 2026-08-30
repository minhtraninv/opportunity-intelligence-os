(() => {
  const esc = (value) => String(value ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const safe = (value) => { try { const u = new URL(value); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };

  const tensionLabel = {
    high: 'TENSION CAO',
    material: 'PHẢN CHỨNG ĐÁNG KỂ',
    watch: 'CẦN THEO DÕI',
    no_verified_counter_signal: 'CHƯA CÓ PHẢN CHỨNG XÁC MINH'
  };

  function ensure(){
    const summary = document.getElementById('moneyFlowSummary');
    if(!summary) return null;
    let grid = document.getElementById('contradictionGrid');
    if(grid) return grid;
    summary.insertAdjacentHTML('afterend', `
      <div id="contradictionHead" class="section-head" style="margin-top:24px">
        <div><div class="eyebrow">WHAT COULD BE WRONG? · V2.3</div><h2>Phản chứng bắt buộc đi cùng thesis</h2></div>
        <span id="contradictionStatus" class="muted">Đang kiểm tra counter-signals…</span>
      </div>
      <div class="panel" style="margin-bottom:14px">
        <strong>Quy tắc:</strong> phản chứng không tự động đảo ngược thesis. Nó buộc hệ thống nêu rõ narrative đang yếu ở đâu và dữ liệu nào sẽ khiến thesis bị hạ cấp.
      </div>
      <div id="contradictionGrid" class="signal-grid" style="margin-bottom:20px"></div>`);
    return document.getElementById('contradictionGrid');
  }

  function signalHtml(x){
    return `<li style="margin-bottom:10px">
      <strong>${esc(x.title || '—')}</strong>
      <div class="muted small" style="margin-top:3px">${esc(x.interpretation || '')}</div>
      ${x.falsifies_if ? `<div class="small" style="margin-top:4px"><strong>Hạ thesis nếu:</strong> ${esc(x.falsifies_if)}</div>` : ''}
      ${x.source_url ? `<a href="${esc(safe(x.source_url))}" target="_blank" rel="noopener noreferrer">nguồn chính thức</a>` : ''}
    </li>`;
  }

  function card(row){
    return `<article class="signal-card">
      <div class="signal-top">
        <div>
          <div class="eyebrow">${esc(tensionLabel[row.tension_level] || row.tension_level)}</div>
          <div class="signal-title">${esc(row.theme_label)}</div>
          <div class="signal-meta">
            <span class="pill">${esc(row.counter_signal_count)} counter-signals</span>
            <span class="pill">Theme ${esc(row.original_score)}</span>
            <span class="pill">After tension ${esc(row.tension_adjusted_score)}</span>
          </div>
        </div>
      </div>
      ${(row.counter_signals || []).length ? `<ul class="plain-list" style="margin-top:10px">${row.counter_signals.map(signalHtml).join('')}</ul>` : '<div class="muted" style="margin-top:9px">Chưa có counter-signal xác minh. Điều này không có nghĩa thesis đúng.</div>'}
      <div class="muted small" style="margin-top:8px">${esc(row.rule || '')}</div>
    </article>`;
  }

  fetch('data/contradiction_intelligence.json', {cache:'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if(!data) return;
      const grid = ensure();
      if(!grid) return;
      const c = data.coverage || {};
      document.getElementById('contradictionStatus').textContent = `${c.verified_counter_signals ?? 0} phản chứng · ${c.themes_with_counter_signals ?? 0} themes bị giới hạn · ${c.regional_production_capital_divergences ?? 0} phân kỳ vùng`;
      const rows = (data.themes || []).filter(x => x.counter_signal_count > 0).slice(0,5);
      grid.innerHTML = rows.length ? rows.map(card).join('') : '<div class="panel muted">Chưa có counter-signal xác minh. Không suy ra thesis là đúng.</div>';
    })
    .catch(() => {});
})();
