(() => {
  const esc = (value) => String(value ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const safe = (value) => { try { const u = new URL(value); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };

  const labels = {
    dual_acceleration: 'GIA TỐC KÉP',
    production_strong_capital_cooling: 'SẢN XUẤT MẠNH · FDI HẠ NHIỆT',
    production_acceleration_capital_unconfirmed: 'SẢN XUẤT TĂNG · CHƯA XÁC NHẬN VỐN',
    capital_acceleration_sector_unconfirmed: 'FDI TĂNG · CHƯA XÁC NHẬN NGÀNH',
    dual_positive: 'CÙNG CHIỀU TÍCH CỰC',
    mixed_confirmed: 'MIXED',
    capital_cooling_production_unconfirmed: 'FDI HẠ NHIỆT · THIẾU PRODUCTION DATA',
    capital_positive_production_unconfirmed: 'FDI TÍCH CỰC · THIẾU PRODUCTION DATA'
  };

  function ensure(){
    const summary = document.getElementById('moneyFlowSummary');
    const themes = document.getElementById('moneyFlowThemes');
    if(!summary || !themes) return null;
    let box = document.getElementById('regionalFlow');
    if(box) return box;
    const html = `
      <div id="regionalFlowHead" class="section-head" style="margin-top:24px">
        <div><div class="eyebrow">REGIONAL MONEY FLOW · V2.2</div><h2>Tiền và sản xuất đang hội tụ ở đâu?</h2></div>
        <span id="regionalFlowStatus" class="muted">Đang đối chiếu IIP + FDI…</span>
      </div>
      <div id="regionalThesis" class="panel" style="margin-bottom:14px"></div>
      <div id="regionalFlow" class="signal-grid" style="margin-bottom:24px"></div>`;
    themes.insertAdjacentHTML('beforebegin', html);
    return document.getElementById('regionalFlow');
  }

  function fmt(value, suffix=''){
    return value == null ? '—' : `${Number(value).toLocaleString('vi-VN', {maximumFractionDigits:1})}${suffix}`;
  }

  function card(x){
    const iipUrl = x.evidence?.iip_source_url;
    const fdiUrl = x.evidence?.fdi_source_url;
    return `<article class="signal-card">
      <div class="signal-top">
        <div>
          <div class="eyebrow">${esc(labels[x.state] || String(x.state || '').toUpperCase())}</div>
          <div class="signal-title">${esc(x.region)}</div>
          <div class="signal-meta">
            <span class="pill">IIP 7T: ${esc(fmt(x.iip_7m_yoy_pct,'%'))}</span>
            <span class="pill">FDI: ${esc(fmt(x.fdi_7m_usd_m,' triệu USD'))}</span>
            <span class="pill">FDI YoY: ${esc(fmt(x.fdi_yoy_pct,'%'))}</span>
          </div>
        </div>
        <div class="signal-score ${x.priority_score >= 80 ? 'hot' : ''}">${esc(x.priority_score)}</div>
      </div>
      <div class="signal-why" style="margin-top:9px">${esc(x.interpretation)}</div>
      <details style="margin-top:9px">
        <summary style="cursor:pointer;font-weight:700">Cần xác minh tiếp</summary>
        <ul class="plain-list" style="margin-top:7px">${(x.next_proxies || []).map(v => `<li>${esc(v)}</li>`).join('')}</ul>
      </details>
      <div class="evidence-links" style="margin-top:9px">
        ${iipUrl ? `<a href="${esc(safe(iipUrl))}" target="_blank" rel="noopener noreferrer">Nguồn IIP</a>` : ''}
        ${fdiUrl ? `<a href="${esc(safe(fdiUrl))}" target="_blank" rel="noopener noreferrer">Nguồn FDI</a>` : ''}
      </div>
    </article>`;
  }

  fetch('data/regional_intelligence.json', {cache:'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if(!data) return;
      const grid = ensure();
      if(!grid) return;
      const c = data.coverage || {};
      document.getElementById('regionalFlowStatus').textContent = `${c.regions ?? 0} địa bàn · ${c.dual_acceleration ?? 0} gia tốc kép · ${c.production_strong_capital_cooling ?? 0} phân kỳ`;
      document.getElementById('regionalThesis').innerHTML = `<div class="eyebrow">REGIONAL THESIS</div><div class="thesis-text" style="margin-top:7px">${esc(data.thesis || '—')}</div><div class="muted small" style="margin-top:7px">Score = mức đáng điều tra, không phải kỳ vọng lợi nhuận. FDI địa phương là tổng FDI, chưa mặc định là manufacturing FDI.</div>`;
      grid.innerHTML = (data.regions || []).slice(0,8).map(card).join('') || '<div class="panel muted">Chưa đủ regional evidence.</div>';
    })
    .catch(() => {});
})();
