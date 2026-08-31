(() => {
  const audit = window.OIAuditUI || {};
  const esc = audit.esc || ((v)=>String(v ?? ''));
  const themeId = audit.themeId || ((t)=>t?.id || t?.theme_id || '');

  const KIND_LABEL = {daily:'Daily Intelligence Brief',weekly:'Weekly Intelligence Report',monthly:'Monthly Regime Review'};
  const STATE_LABEL = {live_today:'LIVE TODAY',week_to_date:'WEEK TO DATE',month_to_date:'MONTH TO DATE',final:'FINAL'};
  let payload=null, activeKind='daily';
  let context={money:null,regional:null,contradiction:null,convergence:null,coverage:null};

  const themes = () => context.money?.themes || [];
  const themeByLabel = (label) => themes().find(t=>String(t.label||'')===String(label||''));
  const entityByLabel = (label) => (context.convergence?.entities||[]).find(e=>String(e.label||'')===String(label||''));
  const regionByName = (name) => (context.regional?.regions||[]).find(r=>String(r.region||'')===String(name||''));
  const contradictionByLabel = (label) => (context.contradiction?.themes||[]).find(x=>String(x.theme_label||'')===String(label||''));
  const coverageByLabel = (label) => (context.coverage?.domains||[]).find(x=>String(x.label||'')===String(label||''));
  const cMap = () => Object.fromEntries((context.contradiction?.themes||[]).map(x=>[x.theme_id,x]));

  function list(items){ return `<ul class="report-list">${(items||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`; }
  function upstreamFor(subject){
    const t=themeByLabel(subject); if(t && audit.evidenceDetails) return audit.evidenceDetails(t,cMap()[themeId(t)]);
    const e=entityByLabel(subject); if(e && audit.entityDetails) return audit.entityDetails(e);
    const r=regionByName(subject); if(r && audit.regionDetails) return audit.regionDetails(r);
    const c=contradictionByLabel(subject); if(c && audit.contradictionDetails) return audit.contradictionDetails(c);
    return '';
  }

  function changedCards(items){
    if(!(items||[]).length) return '<div class="panel muted">Chưa có thay đổi material đủ rõ để liệt kê.</div>';
    return `<div class="report-grid">${items.map(x=>`<article class="panel report-card"><div class="overview-kicker">${esc((x.type||'change').toUpperCase())}</div><h3>${esc(x.title)}</h3><p>${esc(x.assessment)}</p>${upstreamFor(x.title)}</article>`).join('')}</div>`;
  }
  function entityCards(items){
    if(!(items||[]).length) return '<div class="panel muted">Chưa có entity nào vượt primary-evidence gate để đưa vào report.</div>';
    return `<div class="report-grid">${items.map(x=>{const e=entityByLabel(x.label);return `<article class="panel report-card"><div class="overview-kicker">ENTITY · ${esc((x.status||'watch').toUpperCase())}</div><h3>${esc(x.label)}</h3><p>${esc(x.why||'Đang tích lũy evidence.')}</p><div class="report-metrics"><span>Score ${esc(x.score??'—')}</span><span>Primary ${esc(x.primary_evidence??0)}</span><span>Media ${esc(x.media_evidence??0)}</span></div><div class="report-question"><strong>Cần hỏi:</strong> ${esc(x.question||'')}</div>${e&&audit.entityDetails?audit.entityDetails(e):''}</article>`;}).join('')}</div>`;
  }
  function regionCards(items){
    if(!(items||[]).length) return '<div class="panel muted">Chưa có regional divergence đủ rõ.</div>';
    return `<div class="report-grid">${items.map(x=>{const r=regionByName(x.region);return `<article class="panel report-card"><div class="overview-kicker">REGION · ${esc((x.state||'watch').replaceAll('_',' ').toUpperCase())}</div><h3>${esc(x.region)}</h3><p>${esc(x.interpretation||'')}</p><div class="report-metrics"><span>IIP ${x.iip_yoy==null?'—':`${x.iip_yoy>0?'+':''}${esc(x.iip_yoy)}%`}</span><span>FDI ${x.fdi_yoy==null?'—':`${x.fdi_yoy>0?'+':''}${esc(x.fdi_yoy)}%`}</span></div>${x.next_proxy?`<div class="report-question"><strong>Proxy tiếp theo:</strong> ${esc(x.next_proxy)}</div>`:''}${r&&audit.regionDetails?audit.regionDetails(r):''}</article>`;}).join('')}</div>`;
  }
  function contradictionCards(items){
    if(!(items||[]).length) return '<div class="panel muted">Chưa có phản chứng verified nổi bật trong report kỳ này.</div>';
    return `<div class="report-grid">${items.map(x=>{const c=contradictionByLabel(x.theme);return `<article class="panel report-card report-counter"><div class="overview-kicker">FALSIFICATION · ${esc((x.tension||'watch').toUpperCase())}</div><h3>${esc(x.theme)}</h3><p>${esc(x.reading||'Cần đọc thesis cùng counter-evidence.')}</p>${list(x.counter_signals||[])}${c&&audit.contradictionDetails?audit.contradictionDetails(c):''}</article>`;}).join('')}</div>`;
  }
  function coverageDetails(x){
    const d=coverageByLabel(x.domain); if(!d) return '';
    const healthy=d.healthy_source_names||[], productive=d.productive_source_names||[], broken=d.broken_source_names||[];
    return `<details class="evidence-drilldown"><summary>${esc(`${healthy.length} nguồn healthy · ${productive.length} productive · ${broken.length} broken`)}</summary><div class="evidence-audit-body"><div class="evidence-audit-head">Nguồn healthy</div><div class="evidence-meta">${esc(healthy.join(' · ')||'—')}</div><div class="evidence-audit-head">Nguồn productive verified</div><div class="evidence-meta">${esc(productive.join(' · ')||'—')}</div>${broken.length?`<div class="evidence-audit-head">Nguồn lỗi</div><div class="evidence-meta">${esc(broken.join(' · '))}</div>`:''}<div class="evidence-audit-head">Evidence standard</div><div class="evidence-meta">${esc(d.evidence_standard||'—')}</div></div></details>`;
  }
  function blindCards(items){
    if(!(items||[]).length) return '<div class="panel muted">Không có blind spot critical được ghi nhận.</div>';
    return `<div class="report-grid">${items.map(x=>`<article class="panel report-card report-blind"><div class="overview-kicker">SOURCE · ${esc((x.status||'unknown').toUpperCase())}</div><h3>${esc(x.domain)}</h3><p>${esc(x.coverage_note||x.why||'')}</p>${(x.planned_next_sources||[]).length?`<div class="muted small">Next: ${esc(x.planned_next_sources.join(' · '))}</div>`:''}${coverageDetails(x)}</article>`).join('')}</div>`;
  }
  function queue(items){
    if(!(items||[]).length) return '<div class="panel muted">Chưa có câu hỏi ưu tiên.</div>';
    return `<ol class="report-questions">${items.map(x=>`<li><span class="report-qtype">${esc((x.priority||'research').toUpperCase())}</span><strong>${esc(x.subject||'')}</strong><div>${esc(x.question||'')}</div>${upstreamFor(x.subject)}</li>`).join('')}</ol>`;
  }
  function deltaStrip(delta){
    if(delta?.locked) return '<div class="report-delta muted">So sánh kỳ đang khóa vì chưa đủ lịch sử.</div>';
    if(!delta?.available) return '<div class="report-delta muted">Chưa có kỳ trước cùng methodology để so sánh. Snapshot kỳ này là baseline cho kỳ sau.</div>';
    const c=delta.coverage_change||{};
    return `<div class="report-delta"><strong>So với kỳ trước:</strong> ${(delta.theme_changes||[]).length} theme đổi đáng kể · ${(delta.new_entities||[]).length} entity mới · productive sources ${Number(c.productive_sources||0)>=0?'+':''}${esc(c.productive_sources||0)} · source errors ${Number(c.source_errors||0)>=0?'+':''}${esc(c.source_errors||0)}</div>`;
  }

  function lockedView(report,kind){
    const h=report.history_readiness||{};
    return `<article class="panel report-executive report-blind"><div class="eyebrow">${esc(KIND_LABEL[kind])} · MATURITY GATE</div><h2>Chưa đủ lịch sử để tạo báo cáo kỳ này.</h2><p>${esc(report.trust_notice||`Hiện mới có ${h.observation_days||0}/${h.recommended_days||'—'} ngày quan sát.`)}</p>${list(report.executive_summary||[])}<div class="muted small">Không có pseudo-trend: hệ thống chủ động để trống thay vì suy diễn từ vài snapshot.</div></article><div class="section-head report-section"><div><div class="eyebrow">BLIND SPOTS</div><h2>Trong lúc chờ history, hệ thống vẫn phải nói nó đang mù ở đâu</h2></div></div>${blindCards(report.blind_spots)}`;
  }

  function render(kind){
    activeKind=kind;
    document.querySelectorAll('.report-period').forEach(btn=>btn.classList.toggle('active',btn.dataset.reportKind===kind));
    const report=payload?.reports?.[kind], root=document.getElementById('reportBody'), status=document.getElementById('reportStatus');
    if(!root||!status) return;
    if(!report){status.textContent='Report chưa được pipeline tạo.';root.innerHTML='<div class="panel muted">Đang chờ report dataset.</div>';return;}
    const h=report.history_readiness||{}, ready=report.analysis_status==='history_ready', locked=report.analysis_status==='locked_learning_history';
    const maturity=ready?'HISTORY READY':locked?`LOCKED ${h.observation_days||0}/${h.recommended_days||'—'} ngày`:`CURRENT STATE ${h.observation_days||0}/${h.recommended_days||'—'} ngày`;
    status.textContent=`${STATE_LABEL[report.period_state]||report.period_state} · ${maturity}`;
    if(locked){root.innerHTML=lockedView(report,kind);return;}
    root.innerHTML=`
      <article class="panel report-executive"><div class="report-headline-row"><div><div class="eyebrow">${esc(KIND_LABEL[kind])} · ${esc(report.period_key)}</div><h2>${ready?'Điều gì thực sự thay đổi trong cách hệ thống hiểu nền kinh tế?':'Trạng thái hiện tại — chưa được gọi là trend theo kỳ'}</h2></div><span class="report-history-badge ${ready?'ready':'learning'}">${ready?'HISTORY READY':'CURRENT STATE ONLY'}</span></div><div class="report-question"><strong>Trust notice:</strong> ${esc(report.trust_notice||'')}</div>${list(report.executive_summary||[])}${deltaStrip(report.period_delta)}<div class="muted small">${esc(report.reading_rule||'')}</div></article>
      <div class="section-head report-section"><div><div class="eyebrow">WHAT CHANGED</div><h2>${ready?'Thay đổi đáng kể':'Quan sát hiện tại'}</h2></div></div>${changedCards(report.what_changed)}
      <div class="section-head report-section"><div><div class="eyebrow">VERIFIED ENTITY WATCH</div><h2>Ai/cái gì đã vượt primary-evidence gate?</h2></div></div>${entityCards(report.entity_watch)}
      <div class="section-head report-section"><div><div class="eyebrow">REGIONAL DIVERGENCE</div><h2>Địa bàn đáng chú ý</h2></div></div>${regionCards(report.regional_watch)}
      <div class="section-head report-section"><div><div class="eyebrow">WHAT COULD BE WRONG</div><h2>Phản chứng và điều có thể khiến thesis sai</h2></div></div>${contradictionCards(report.contradictions)}
      <div class="section-head report-section"><div><div class="eyebrow">BLIND SPOTS</div><h2>Điều hệ thống vẫn chưa nhìn đủ</h2></div></div>${blindCards(report.blind_spots)}
      <div class="section-head report-section"><div><div class="eyebrow">NEXT INVESTIGATIONS</div><h2>Những câu hỏi đáng bỏ thời gian tiếp theo</h2></div></div>${queue(report.investigation_queue)}`;
  }

  document.querySelectorAll('.report-period').forEach(btn=>btn.addEventListener('click',()=>render(btn.dataset.reportKind)));

  Promise.all([
    fetch('data/intelligence_reports.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`report HTTP ${r.status}`);return r.json();}),
    fetch('data/money_flow_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/regional_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/contradiction_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/entity_convergence_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/source_coverage_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)
  ]).then(([data,money,regional,contradiction,convergence,coverage])=>{
    payload=data; context={money,regional,contradiction,convergence,coverage};
    const count=document.getElementById('reportHistoryCount'); if(count) count.textContent=`${data.history_count||0} period snapshots`;
    render(activeKind);
  }).catch(err=>{
    const status=document.getElementById('reportStatus'), root=document.getElementById('reportBody');
    if(status) status.textContent='REPORT DATA ERROR'; if(root) root.innerHTML=`<div class="panel muted">Chưa tải được report: ${esc(err.message)}</div>`;
  });
})();