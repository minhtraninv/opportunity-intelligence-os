(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');

  const KIND_LABEL = {
    daily: 'Daily Intelligence Brief',
    weekly: 'Weekly Intelligence Report',
    monthly: 'Monthly Regime Review',
  };

  const STATE_LABEL = {
    live_today: 'LIVE TODAY',
    week_to_date: 'WEEK TO DATE',
    month_to_date: 'MONTH TO DATE',
    final: 'FINAL',
  };

  let payload = null;
  let activeKind = 'weekly';

  function list(items){
    return `<ul class="report-list">${(items || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
  }

  function changedCards(items){
    if(!(items || []).length) return '<div class="panel muted">Chưa có thay đổi material đủ rõ để liệt kê.</div>';
    return `<div class="report-grid">${items.map(x => `
      <article class="panel report-card">
        <div class="overview-kicker">${esc((x.type || 'change').toUpperCase())}</div>
        <h3>${esc(x.title)}</h3>
        <p>${esc(x.assessment)}</p>
      </article>`).join('')}</div>`;
  }

  function entityCards(items){
    if(!(items || []).length) return '<div class="panel muted">Chưa có entity vượt ngưỡng watch.</div>';
    return `<div class="report-grid">${items.map(x => `
      <article class="panel report-card">
        <div class="overview-kicker">ENTITY · ${esc((x.status || 'watch').toUpperCase())}</div>
        <h3>${esc(x.label)}</h3>
        <p>${esc(x.why || 'Đang tích lũy evidence.')}</p>
        <div class="report-metrics"><span>Score ${esc(x.score ?? '—')}</span><span>Primary ${esc(x.primary_evidence ?? 0)}</span><span>Media ${esc(x.media_evidence ?? 0)}</span></div>
        <div class="report-question"><strong>Cần hỏi:</strong> ${esc(x.question || '')}</div>
      </article>`).join('')}</div>`;
  }

  function regionCards(items){
    if(!(items || []).length) return '<div class="panel muted">Chưa có regional divergence đủ rõ.</div>';
    return `<div class="report-grid">${items.map(x => `
      <article class="panel report-card">
        <div class="overview-kicker">REGION · ${esc((x.state || 'watch').replaceAll('_',' ').toUpperCase())}</div>
        <h3>${esc(x.region)}</h3>
        <p>${esc(x.interpretation || '')}</p>
        <div class="report-metrics"><span>IIP ${x.iip_yoy == null ? '—' : `${x.iip_yoy > 0 ? '+' : ''}${esc(x.iip_yoy)}%`}</span><span>FDI ${x.fdi_yoy == null ? '—' : `${x.fdi_yoy > 0 ? '+' : ''}${esc(x.fdi_yoy)}%`}</span></div>
        ${x.next_proxy ? `<div class="report-question"><strong>Proxy tiếp theo:</strong> ${esc(x.next_proxy)}</div>` : ''}
      </article>`).join('')}</div>`;
  }

  function contradictionCards(items){
    if(!(items || []).length) return '<div class="panel muted">Chưa có phản chứng verified nổi bật trong report kỳ này.</div>';
    return `<div class="report-grid">${items.map(x => `
      <article class="panel report-card report-counter">
        <div class="overview-kicker">FALSIFICATION · ${esc((x.tension || 'watch').toUpperCase())}</div>
        <h3>${esc(x.theme)}</h3>
        <p>${esc(x.reading || 'Cần đọc thesis cùng counter-evidence.')}</p>
        ${list(x.counter_signals || [])}
      </article>`).join('')}</div>`;
  }

  function blindCards(items){
    if(!(items || []).length) return '<div class="panel muted">Không có blind spot critical được ghi nhận.</div>';
    return `<div class="report-grid">${items.map(x => `
      <article class="panel report-card report-blind">
        <div class="overview-kicker">SOURCE · ${esc((x.status || 'unknown').toUpperCase())}</div>
        <h3>${esc(x.domain)}</h3>
        <p>${esc(x.coverage_note || x.why || '')}</p>
        ${(x.planned_next_sources || []).length ? `<div class="muted small">Next: ${esc(x.planned_next_sources.join(' · '))}</div>` : ''}
      </article>`).join('')}</div>`;
  }

  function queue(items){
    if(!(items || []).length) return '<div class="panel muted">Chưa có câu hỏi ưu tiên.</div>';
    return `<ol class="report-questions">${items.map(x => `<li><span class="report-qtype">${esc((x.priority || 'research').toUpperCase())}</span><strong>${esc(x.subject || '')}</strong><div>${esc(x.question || '')}</div></li>`).join('')}</ol>`;
  }

  function deltaStrip(delta){
    if(!delta?.available) return '<div class="report-delta muted">Chưa có kỳ trước cùng loại để so sánh. Snapshot kỳ này sẽ trở thành baseline cho kỳ sau.</div>';
    const c = delta.coverage_change || {};
    const themeCount = (delta.theme_changes || []).length;
    const newEntityCount = (delta.new_entities || []).length;
    return `<div class="report-delta"><strong>So với kỳ trước:</strong> ${themeCount} theme đổi đáng kể · ${newEntityCount} entity mới · productive sources ${Number(c.productive_sources || 0) >= 0 ? '+' : ''}${esc(c.productive_sources || 0)} · source errors ${Number(c.source_errors || 0) >= 0 ? '+' : ''}${esc(c.source_errors || 0)}</div>`;
  }

  function render(kind){
    activeKind = kind;
    document.querySelectorAll('.report-period').forEach(btn => btn.classList.toggle('active', btn.dataset.reportKind === kind));
    const report = payload?.reports?.[kind];
    const root = document.getElementById('reportBody');
    const status = document.getElementById('reportStatus');
    if(!root || !status) return;
    if(!report){
      status.textContent = 'Report chưa được pipeline tạo.';
      root.innerHTML = '<div class="panel muted">Đang chờ report dataset.</div>';
      return;
    }

    const ready = report.history_status === 'ready';
    const h = report.history_readiness || {};
    status.textContent = `${STATE_LABEL[report.period_state] || report.period_state} · ${ready ? 'HISTORY READY' : `LEARNING HISTORY ${h.observation_days || 0}/${h.recommended_days || '—'} ngày`}`;

    root.innerHTML = `
      <article class="panel report-executive">
        <div class="report-headline-row">
          <div>
            <div class="eyebrow">${esc(KIND_LABEL[kind])} · ${esc(report.period_key)}</div>
            <h2>Điều gì thực sự thay đổi trong cách hệ thống hiểu nền kinh tế?</h2>
          </div>
          <span class="report-history-badge ${ready ? 'ready' : 'learning'}">${ready ? 'HISTORY READY' : 'LEARNING HISTORY'}</span>
        </div>
        ${list(report.executive_summary || [])}
        ${deltaStrip(report.period_delta)}
        <div class="muted small">${esc(report.reading_rule || '')}</div>
      </article>

      <div class="section-head report-section"><div><div class="eyebrow">WHAT CHANGED</div><h2>Thay đổi đáng kể</h2></div></div>
      ${changedCards(report.what_changed)}

      <div class="section-head report-section"><div><div class="eyebrow">ENTITY WATCH</div><h2>Ai/cái gì đang đáng mở hồ sơ?</h2></div></div>
      ${entityCards(report.entity_watch)}

      <div class="section-head report-section"><div><div class="eyebrow">REGIONAL DIVERGENCE</div><h2>Địa bàn đáng chú ý</h2></div></div>
      ${regionCards(report.regional_watch)}

      <div class="section-head report-section"><div><div class="eyebrow">WHAT COULD BE WRONG</div><h2>Phản chứng và điều có thể khiến thesis sai</h2></div></div>
      ${contradictionCards(report.contradictions)}

      <div class="section-head report-section"><div><div class="eyebrow">BLIND SPOTS</div><h2>Điều hệ thống vẫn chưa nhìn đủ</h2></div></div>
      ${blindCards(report.blind_spots)}

      <div class="section-head report-section"><div><div class="eyebrow">NEXT INVESTIGATIONS</div><h2>Những câu hỏi đáng bỏ thời gian tiếp theo</h2></div></div>
      ${queue(report.investigation_queue)}
    `;
  }

  document.querySelectorAll('.report-period').forEach(btn => btn.addEventListener('click', () => render(btn.dataset.reportKind)));

  fetch('data/intelligence_reports.json', {cache:'no-store'})
    .then(r => { if(!r.ok) throw new Error(`report HTTP ${r.status}`); return r.json(); })
    .then(data => {
      payload = data;
      const count = document.getElementById('reportHistoryCount');
      if(count) count.textContent = `${data.history_count || 0} period snapshots`;
      render(activeKind);
    })
    .catch(err => {
      const status = document.getElementById('reportStatus');
      const root = document.getElementById('reportBody');
      if(status) status.textContent = 'REPORT DATA ERROR';
      if(root) root.innerHTML = `<div class="panel muted">Chưa tải được report: ${esc(err.message)}</div>`;
    });
})();
