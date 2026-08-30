(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');

  const STATE = {
    strong: 'STRONG',
    partial: 'PARTIAL',
    weak: 'WEAK',
    broken: 'BROKEN',
    missing: 'MISSING'
  };

  function ensureSection(){
    if(document.getElementById('sourceCoverageOverview')) return;
    const reality = document.getElementById('realityOverview');
    if(!reality) return;
    reality.insertAdjacentHTML('afterend', `
      <div class="section-head overview-section">
        <div class="overview-section-copy">
          <div class="eyebrow">8 · SOURCE COVERAGE</div>
          <h2>Hệ thống đang nhìn thấy gì — và còn mù ở đâu?</h2>
          <p class="muted">Intelligence không được phép tự tin hơn dữ liệu đầu vào. Domain thiếu, yếu hoặc lỗi phải được công khai như một blind spot.</p>
        </div>
      </div>
      <div id="sourceCoveragePulse" class="overview-pulse" style="margin-bottom:14px"></div>
      <div id="sourceCoverageOverview" class="overview-grid"></div>
    `);
  }

  function card(x){
    const next = (x.planned_next_sources || []).slice(0,2);
    return `<article class="panel overview-card ${['broken','missing'].includes(x.status) ? 'overview-warning' : ''}">
      <div class="overview-kicker">DATA · ${esc(STATE[x.status] || x.status)} · PRIORITY ${esc(x.priority)}</div>
      <h3>${esc(x.label)}</h3>
      <p>${esc(x.coverage_note)}</p>
      <div class="overview-path-metrics">
        <span class="pill">Healthy ${esc(x.healthy_sources)}/${esc(x.target_healthy_sources)}</span>
        <span class="pill">Evidence ${esc(x.evidence_items_this_run)}</span>
        ${x.broken_sources ? `<span class="pill">Broken ${esc(x.broken_sources)}</span>` : ''}
      </div>
      <div class="card-footer muted small">
        ${next.length ? `<strong>Nguồn cần bổ sung:</strong> ${esc(next.join(' · '))}` : esc(x.why || '')}
      </div>
    </article>`;
  }

  ensureSection();
  fetch('data/source_coverage_intelligence.json', {cache:'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if(!data) return;
      const c = data.coverage || {};
      const pulse = document.getElementById('sourceCoveragePulse');
      if(pulse) pulse.innerHTML = `
        <div class="overview-pulse-item"><span class="muted small">Coverage domains</span><strong>${esc(c.domains ?? 0)}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Strong</span><strong>${esc(c.strong ?? 0)}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Partial / Weak</span><strong>${esc((c.partial ?? 0) + (c.weak ?? 0))}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Broken / Missing</span><strong>${esc((c.broken ?? 0) + (c.missing ?? 0))}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Healthy sources</span><strong>${esc(c.healthy_sources ?? 0)}</strong></div>`;

      const grid = document.getElementById('sourceCoverageOverview');
      const domains = data.domains || [];
      const important = domains
        .filter(x => x.status !== 'strong')
        .sort((a,b) => (a.priority-b.priority) || ({missing:0,broken:1,weak:2,partial:3}[a.status] ?? 9) - ({missing:0,broken:1,weak:2,partial:3}[b.status] ?? 9))
        .slice(0,6);
      if(grid) grid.innerHTML = important.length
        ? important.map(card).join('')
        : '<div class="panel muted">Không có blind spot ưu tiên cao ở lần audit này.</div>';
    })
    .catch(() => {});
})();
