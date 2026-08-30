(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const safe = (v) => { try { const u=new URL(v); return ['http:','https:'].includes(u.protocol)?u.href:'#'; } catch { return '#'; } };

  function ensureAttention(){
    if(document.getElementById('attentionOverview')) return;
    const anchor = document.getElementById('attentionAnchor');
    if(!anchor) return;
    anchor.insertAdjacentHTML('afterend', `
      <div class="section-head overview-section attention-head">
        <div class="overview-section-copy">
          <div class="eyebrow">DON'T IGNORE · ATTENTION QUEUE</div>
          <h2>Những thứ đáng mở hồ sơ nghiên cứu lúc này</h2>
          <p class="muted">Không phải tín hiệu mua hay lời khuyên kinh doanh. Đây là hàng đợi những thay đổi có đủ lý do để không nên lướt qua.</p>
        </div>
      </div>
      <div id="attentionOverview" class="attention-grid"></div>
    `);
  }

  function attentionCard(x){
    const source = x.url ? `<a href="${esc(safe(x.url))}" target="_blank" rel="noopener noreferrer">mở nguồn</a>` : '';
    return `<article class="panel attention-card">
      <div class="overview-kicker">${esc(x.kind)} · ${esc(x.level)}</div>
      <h3>${esc(x.title)}</h3>
      <p>${esc(x.why)}</p>
      <div class="attention-question"><strong>Câu hỏi tiếp theo:</strong> ${esc(x.question)}</div>
      <div class="card-footer muted small">${source}${source && x.evidence ? ' · ' : ''}${esc(x.evidence || '')}</div>
    </article>`;
  }

  function buildQueue({policy,money,regional,convergence,corporate,contradiction}){
    const out = [];
    const cMap = Object.fromEntries((contradiction?.themes || []).map(x=>[x.theme_id,x]));

    const entities = (convergence?.entities || []).filter(x=>x.status!=='not_observed');
    entities
      .sort((a,b)=>(b.convergence_score||0)-(a.convergence_score||0))
      .slice(0,2)
      .forEach(e=>{
        const primary = Number(e.primary_evidence_count||0);
        const media = Number(e.media_evidence_count||0);
        out.push({
          kind:'ENTITY',
          level:e.status==='watch'?'WATCH':'INVESTIGATE',
          title:e.label,
          why:e.why_now,
          question:(e.investigation_questions||[])[primary===0?3:2] || 'Driver nào đang thực sự thay đổi economics của entity này?',
          evidence:`Primary ${primary} · Media ${media} · ${(e.evidence_families||[]).length} họ bằng chứng`,
          url:(e.evidence||[])[0]?.source_url
        });
      });

    (money?.themes || []).slice().sort((a,b)=>{
      const aa=cMap[a.theme_id]?.tension_adjusted_score ?? a.score ?? 0;
      const bb=cMap[b.theme_id]?.tension_adjusted_score ?? b.score ?? 0;
      return bb-aa;
    }).slice(0,2).forEach(t=>{
      const adjusted = cMap[t.theme_id]?.tension_adjusted_score ?? t.score;
      out.push({
        kind:'MONEY FLOW', level:t.status==='converging'?'CONVERGING':'WATCH', title:t.label,
        why:(t.economic_chain||[]).slice(0,2).join(' → ') || `Theme score ${adjusted}`,
        question:'Dòng tiền này đã chuyển thành buyer, CAPEX, hiring hoặc economics quan sát được ở đâu?',
        evidence:`Score sau phản chứng ${adjusted} · ${(t.independent_families||[]).length} evidence families`
      });
    });

    (regional?.regions || []).filter(r=>r.state==='dual_acceleration').slice(0,1).forEach(r=>out.push({
      kind:'REGION', level:'DIVERGENCE', title:r.region,
      why:r.interpretation,
      question:(r.next_proxies||[])[0] || 'Tăng trưởng này đến từ vốn mới hay công suất đã đầu tư trước đó?',
      evidence:`IIP ${r.iip_7m_yoy_pct>0?'+':''}${r.iip_7m_yoy_pct}% · FDI YoY ${r.fdi_yoy_pct>0?'+':''}${r.fdi_yoy_pct}%`,
      url:r.evidence?.fdi_source_url || r.evidence?.iip_source_url
    }));

    const corp = corporate?.recent_events || [];
    if(corp.length){
      const e = corp[0];
      out.push({
        kind:'CORPORATE ACTION', level:'PRIMARY TRIGGER', title:`${e.ticker} · ${e.title}`,
        why:'Công bố chính thức cho thấy một hành động vốn/dự án/hợp đồng cần được đặt vào bối cảnh rộng hơn trước khi kết luận.',
        question:'Quy mô, nguồn vốn, thời điểm thực thi và tác động kinh tế thực của sự kiện này là gì?',
        evidence:e.publisher || 'HNX official disclosure', url:e.source_url
      });
    }

    if(out.length < 5){
      const p=(policy?.structural_policies||[]).slice().sort((a,b)=>(b.strategic_relevance||0)-(a.strategic_relevance||0))[0];
      if(p) out.push({
        kind:'POLICY', level:'STRUCTURAL', title:p.title, why:p.mechanism,
        question:(p.watch_next||[])[0] || 'Cơ chế thực thi nào sẽ biến định hướng này thành dòng tiền thật?',
        evidence:`Strategic relevance ${p.strategic_relevance}`, url:p.source_url
      });
    }
    return out.slice(0,6);
  }

  function normalizeExecutionTab(){
    const apply = () => {
      const tab=document.querySelector('.tab[data-tab="edge"]');
      if(tab) tab.textContent='Execution Profile';
      const edge=document.getElementById('edge');
      const h=edge?.querySelector('.section-head h2');
      if(h) h.textContent='Profile thực thi cho Advanced campaigns';
      const eye=edge?.querySelector('.section-head .eyebrow');
      if(eye) eye.textContent='ADVANCED EXECUTION PROFILE';
    };
    apply();
    const nav=document.querySelector('.tabs');
    if(nav){ const obs=new MutationObserver(apply); obs.observe(nav,{childList:true,subtree:true}); setTimeout(()=>obs.disconnect(),6000); }
  }

  ensureAttention();
  normalizeExecutionTab();

  Promise.all([
    fetch('data/policy_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/money_flow_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/regional_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/entity_convergence_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/corporate_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/contradiction_intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)
  ]).then(([policy,money,regional,convergence,corporate,contradiction])=>{
    const grid=document.getElementById('attentionOverview');
    if(!grid) return;
    const rows=buildQueue({policy,money,regional,convergence,corporate,contradiction});
    grid.innerHTML=rows.length?rows.map(attentionCard).join(''):'<div class="panel muted">Chưa có thay đổi nào vượt ngưỡng để đưa vào hàng đợi. Không có alert cũng là một kết quả hợp lệ.</div>';
  });
})();
