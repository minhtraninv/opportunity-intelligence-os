(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const STATE = {strong:'STRONG',partial:'PARTIAL',weak:'WEAK',broken:'BROKEN',missing:'MISSING'};

  function setText(id,value){ const el=document.getElementById(id); if(el) el.textContent=value; }
  function ensureSection(){
    if(document.getElementById('sourceCoverageOverview')) return;
    const overview=document.getElementById('overview');
    if(!overview) return;
    const advanced=[...overview.querySelectorAll('.overview-advanced-note')].pop();
    const html=`
      <div class="section-head overview-section source-coverage-head">
        <div class="overview-section-copy">
          <div class="eyebrow">8 · SOURCE COVERAGE</div>
          <h2>Hệ thống đang nhìn thấy gì — và còn mù ở đâu?</h2>
          <p class="muted">Source health, discovery coverage và verified evidence là ba lớp khác nhau. Website truy cập được chưa có nghĩa nó đã tạo intelligence đủ cấp.</p>
        </div>
      </div>
      <div id="sourceCoveragePulse" class="overview-pulse" style="margin-bottom:14px"></div>
      <div id="sourceCoverageOverview" class="overview-grid"></div>`;
    if(advanced) advanced.insertAdjacentHTML('afterend',html); else overview.insertAdjacentHTML('beforeend',html);
  }
  function card(x){
    const next=(x.planned_next_sources||[]).slice(0,3);
    const healthy=x.healthy_source_names||[], verified=x.productive_source_names||[], broken=x.broken_source_names||[];
    return `<article class="panel overview-card ${['broken','missing'].includes(x.status)?'overview-warning':''}">
      <div class="overview-kicker">DATA · ${esc(STATE[x.status]||x.status)} · PRIORITY ${esc(x.priority)}</div>
      <h3>${esc(x.label)}</h3><p>${esc(x.coverage_note)}</p>
      <div class="overview-path-metrics">
        <span class="pill">Healthy ${esc(x.healthy_sources)}/${esc(x.target_healthy_sources)}</span>
        <span class="pill">Verified productive ${esc(x.verified_productive_sources??0)}</span>
        <span class="pill">Discovery productive ${esc(x.discovery_productive_sources??0)}</span>
        <span class="pill">Verified evidence ${esc(x.verified_evidence_items_this_run??x.evidence_items_this_run??0)}</span>
        ${x.discovery_evidence_items_this_run?`<span class="pill">Discovery ${esc(x.discovery_evidence_items_this_run)}</span>`:''}
        ${x.broken_sources?`<span class="pill">Broken ${esc(x.broken_sources)}</span>`:''}
      </div>
      <details class="evidence-drilldown"><summary>${esc(`${healthy.length} nguồn healthy · ${verified.length} verified productive · ${broken.length} lỗi`)}</summary>
        <div class="evidence-audit-body">
          <div class="evidence-audit-head">Evidence standard</div><div class="evidence-meta">${esc(x.evidence_standard||'—')}</div>
          <div class="evidence-audit-head">Nguồn healthy</div><div class="evidence-meta">${esc(healthy.join(' · ')||'—')}</div>
          <div class="evidence-audit-head">Nguồn tạo verified evidence</div><div class="evidence-meta">${esc(verified.join(' · ')||'—')}</div>
          ${broken.length?`<div class="evidence-audit-head">Nguồn đang lỗi</div><div class="evidence-meta">${esc(broken.join(' · '))}</div>`:''}
          <div class="evidence-audit-head">Vì sao domain này quan trọng?</div><div class="evidence-meta">${esc(x.why||'—')}</div>
        </div>
      </details>
      <div class="card-footer muted small">${next.length?`<strong>Nguồn cần bổ sung:</strong> ${esc(next.join(' · '))}`:esc(x.why||'')}</div>
    </article>`;
  }

  ensureSection();
  fetch('data/source_coverage_intelligence.json',{cache:'no-store'})
    .then(r=>r.ok?r.json():null)
    .then(data=>{
      if(!data) return;
      const c=data.coverage||{};
      const blind=(c.partial??0)+(c.weak??0)+(c.broken??0)+(c.missing??0);
      setText('coverageStrongSidebar',`${c.strong??0}/${c.domains??0}`);
      setText('coverageBlindSidebar',blind);
      setText('coverageProductiveSidebar',c.verified_productive_sources??c.productive_sources??0);
      setText('coverageErrorsSidebar',c.source_errors??0);

      const pulse=document.getElementById('sourceCoveragePulse');
      if(pulse) pulse.innerHTML=`
        <div class="overview-pulse-item"><span class="muted small">Coverage domains</span><strong>${esc(c.domains??0)}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Strong</span><strong>${esc(c.strong??0)}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Partial / Weak</span><strong>${esc((c.partial??0)+(c.weak??0))}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Broken / Missing</span><strong>${esc((c.broken??0)+(c.missing??0))}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Verified productive</span><strong>${esc(c.verified_productive_sources??c.productive_sources??0)}</strong></div>
        <div class="overview-pulse-item"><span class="muted small">Discovery productive</span><strong>${esc(c.discovery_productive_sources??0)}</strong></div>`;

      const domains=data.domains||[];
      const severity={missing:0,broken:1,weak:2,partial:3,strong:9};
      const important=domains.filter(x=>x.status!=='strong').sort((a,b)=>(a.priority-b.priority)||(severity[a.status]-severity[b.status])).slice(0,8);
      const grid=document.getElementById('sourceCoverageOverview');
      if(grid) grid.innerHTML=important.length?important.map(card).join(''):'<div class="panel muted">Không có blind spot ưu tiên cao ở lần audit này.</div>';
    }).catch(()=>{});
})();