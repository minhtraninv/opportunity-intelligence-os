(() => {
  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const safeUrl = (value) => {
    try {
      const u = new URL(value);
      return ['http:', 'https:'].includes(u.protocol) ? u.href : '#';
    } catch { return '#'; }
  };

  function ensureView(){
    const tabs = document.querySelector('.tabs');
    const content = document.querySelector('.content');
    if(!tabs || !content) return null;

    let button = document.querySelector('[data-tab="moneyflow"]');
    if(!button){
      button = document.createElement('button');
      button.className = 'tab';
      button.dataset.tab = 'moneyflow';
      button.textContent = 'Money Flow';
      const today = tabs.querySelector('[data-tab="today"]');
      if(today?.nextSibling) tabs.insertBefore(button, today.nextSibling);
      else tabs.appendChild(button);
    }

    let view = document.getElementById('moneyflow');
    if(!view){
      view = document.createElement('section');
      view.id = 'moneyflow';
      view.className = 'tab-view';
      view.innerHTML = `
        <div class="section-head">
          <div>
            <div class="eyebrow">VIETNAM MONEY FLOW INTELLIGENCE · V2.0</div>
            <h2>Từ tín hiệu rời rạc thành chuyển động kinh tế</h2>
          </div>
          <span id="moneyFlowStatus" class="muted">Đang dựng theme graph…</span>
        </div>
        <div class="panel" style="margin-bottom:16px">
          <strong>Cách đọc:</strong> theme chỉ nói nơi bằng chứng đang hội tụ. Theme ≠ cơ hội. Không có dữ liệu cung ≠ thiếu cung. Chỉ khi xác minh buyer + economics + supply gap + small test thì mới được nâng thành opportunity.
        </div>
        <div id="moneyFlowSummary" class="panel" style="margin-bottom:18px"></div>
        <div id="moneyFlowThemes" class="signal-grid"></div>`;
      const signals = document.getElementById('signals');
      content.insertBefore(view, signals || null);
    }

    button.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-view').forEach(x => x.classList.remove('active'));
      button.classList.add('active');
      view.classList.add('active');
    });
    return view;
  }

  function statusLabel(value){
    return ({
      converging: 'HỘI TỤ ĐA NGUỒN',
      developing: 'ĐANG HÌNH THÀNH',
      early: 'TÍN HIỆU SỚM',
      insufficient: 'CHƯA ĐỦ BẰNG CHỨNG'
    })[value] || String(value || '—').toUpperCase();
  }

  function gapLabel(value){
    return ({
      confirmed_gap: 'SUPPLY GAP ĐÃ XÁC NHẬN',
      investigate_gap: 'CẦN ĐIỀU TRA CUNG',
      unconfirmed_supply_gap: 'SUPPLY GAP CHƯA XÁC NHẬN'
    })[value] || 'SUPPLY GAP CHƯA XÁC NHẬN';
  }

  function evidenceHtml(items){
    return (items || []).slice(0,6).map(x => `
      <li style="margin-bottom:7px">
        <strong>${esc(x.family || 'evidence')}:</strong> ${esc(x.title || '—')}
        ${x.publisher ? `<span class="muted"> · ${esc(x.publisher)}</span>` : ''}
        ${x.source_url ? ` · <a href="${esc(safeUrl(x.source_url))}" target="_blank" rel="noopener noreferrer">nguồn</a>` : ''}
      </li>`).join('');
  }

  function themeCard(theme){
    const families = (theme.independent_families || []).join(' · ') || '—';
    const chain = (theme.economic_chain || []).map((x,i) => `<li><strong>${i+1}.</strong> ${esc(x)}</li>`).join('');
    const angles = (theme.small_capital_angles || []).map(x => `<li>${esc(x)}</li>`).join('');
    const proxies = (theme.supply_gap?.proxies_needed || []).map(x => `<li>${esc(x)}</li>`).join('');
    return `<article class="signal-card">
      <div class="signal-top">
        <div>
          <div class="eyebrow">${esc(statusLabel(theme.status))} · ${esc(theme.evidence_count)} EVIDENCE</div>
          <div class="signal-title">${esc(theme.label)}</div>
          <div class="signal-meta">
            <span class="pill">Families: ${esc((theme.independent_families || []).length)}</span>
            <span class="pill">Publishers: ${esc((theme.independent_publishers || []).length)}</span>
            <span class="pill">${esc(gapLabel(theme.supply_gap?.status))}</span>
          </div>
        </div>
        <div class="signal-score ${theme.score >= 70 ? 'hot' : ''}">${esc(theme.score)}</div>
      </div>
      <div class="muted small" style="margin-top:8px"><strong>Họ bằng chứng:</strong> ${esc(families)}</div>

      <details style="margin-top:12px" open>
        <summary style="cursor:pointer;font-weight:800">Economic chain — tiền có thể chảy qua đâu?</summary>
        <ol class="plain-list" style="margin-top:9px">${chain}</ol>
      </details>

      <details style="margin-top:10px">
        <summary style="cursor:pointer;font-weight:800">Bằng chứng đang hội tụ</summary>
        <ul class="plain-list" style="margin-top:9px">${evidenceHtml(theme.evidence)}</ul>
      </details>

      <details style="margin-top:10px">
        <summary style="cursor:pointer;font-weight:800">Góc vốn nhỏ cần kiểm chứng</summary>
        <ul class="plain-list" style="margin-top:9px">${angles}</ul>
      </details>

      <div class="panel" style="margin-top:12px;padding:12px">
        <strong>${esc(gapLabel(theme.supply_gap?.status))}</strong>
        <div class="muted small" style="margin-top:5px">${esc(theme.supply_gap?.rule || '')}</div>
        <details style="margin-top:7px">
          <summary style="cursor:pointer">Cần thu thêm dữ liệu cung nào?</summary>
          <ul class="plain-list" style="margin-top:7px">${proxies}</ul>
        </details>
      </div>
    </article>`;
  }

  ensureView();
  fetch('data/money_flow_intelligence.json', {cache:'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if(!data) return;
      ensureView();
      const status = document.getElementById('moneyFlowStatus');
      const summary = document.getElementById('moneyFlowSummary');
      const grid = document.getElementById('moneyFlowThemes');
      const c = data.coverage || {};

      if(status) status.textContent = `${c.total_evidence_inputs ?? 0} evidence · ${c.themes_converging ?? 0} themes hội tụ · ${c.supply_gaps_confirmed ?? 0} gap xác nhận`;
      if(summary) summary.innerHTML = `
        <div class="eyebrow">CURRENT MONEY-FLOW THESIS</div>
        <div class="thesis-text" style="margin-top:7px">${esc(data.thesis || '—')}</div>
        <div class="muted small" style="margin-top:9px">V2.0 ưu tiên họ bằng chứng độc lập hơn số lượng headline. Procurement chỉ là supporting evidence.</div>`;
      if(grid) grid.innerHTML = (data.themes || []).map(themeCard).join('') || '<div class="panel muted">Chưa có theme đủ dữ liệu.</div>';

      const thesis = document.getElementById('thesisText');
      if(thesis && data.thesis) thesis.textContent = data.thesis;
    })
    .catch(() => {});
})();
