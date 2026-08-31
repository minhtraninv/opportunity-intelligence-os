(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const safe = (v) => { try { const u=new URL(v); return ['http:','https:'].includes(u.protocol)?u.href:'#'; } catch { return '#'; } };
  const VERIFIED_QUALITIES = new Set(['official_verified','curated','primary_verified']);
  const FAMILY_LABEL = {
    policy:'Chính sách', capital:'Dòng vốn / FDI', production:'Sản xuất', trade:'Xuất nhập khẩu',
    public_capital:'Đầu tư công', labor:'Lao động', consumption:'Tiêu dùng', energy:'Điện / năng lượng',
    project_execution:'Dự án / thực thi', strategy:'Chiến lược', operating:'Vận hành / demand',
    business_formation:'Hình thành DN', procurement:'Mua sắm công'
  };

  function themeId(t){ return t?.id || t?.theme_id || ''; }

  function ensureAuditStyles(){
    if(document.getElementById('oiEvidenceAuditStyles')) return;
    const style=document.createElement('style');
    style.id='oiEvidenceAuditStyles';
    style.textContent=`
      .evidence-drilldown{margin-top:12px;border-top:1px solid var(--line,#2a394b);padding-top:10px}
      .evidence-drilldown summary{cursor:pointer;color:#8ec9ff;font-weight:800;font-size:12px;list-style:none}
      .evidence-drilldown summary::-webkit-details-marker{display:none}
      .evidence-drilldown summary:before{content:'＋ ';color:var(--green,#37d67a)}
      .evidence-drilldown[open] summary:before{content:'− '}
      .evidence-audit-body{margin-top:10px;padding:11px;border-radius:9px;background:#0b141d}
      .evidence-audit-head{font-size:11px;font-weight:900;letter-spacing:.04em;text-transform:uppercase;color:#9eb1c5;margin:10px 0 6px}
      .evidence-audit-head:first-child{margin-top:0}
      .evidence-row{padding:8px 0;border-top:1px solid rgba(255,255,255,.07);line-height:1.45}
      .evidence-row:first-of-type{border-top:0}
      .evidence-row a{color:#8ec9ff;text-decoration:none}
      .evidence-row a:hover{text-decoration:underline}
      .evidence-meta{font-size:11px;color:#91a2b4;margin-top:3px}
      .counter-row{border-left:2px solid #d8a94e;padding-left:9px}
      .evidence-empty{font-size:12px;color:#91a2b4}
    `;
    document.head.appendChild(style);
  }

  function verifiedEvidence(t){
    return (t?.evidence || []).filter(e => e && VERIFIED_QUALITIES.has(e.quality) && e.family !== 'procurement' && e.directional !== false);
  }

  function evidenceDetails(t,c){
    const verified=verifiedEvidence(t);
    const counters=(c?.counter_signals || []).filter(Boolean);
    const families=t?.verified_evidence_families || t?.independent_families || [];
    const publishers=t?.verified_evidence_publishers || t?.independent_publishers || [];
    const summary=`${verified.length} bằng chứng verified · ${families.length} họ · ${counters.length} phản chứng · xem nguồn`;
    const evidenceHtml=verified.length ? verified.map(e=>{
      const family=FAMILY_LABEL[e.family] || e.family || 'Evidence';
      const title=esc(e.title || 'Bằng chứng');
      const link=safe(e.source_url);
      const titleHtml=link!=='#' ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${title}</a>` : title;
      const period=e.observed_at ? ` · Kỳ ${esc(e.observed_at)}` : '';
      return `<div class="evidence-row">${titleHtml}<div class="evidence-meta">${esc(family)} · ${esc(e.publisher || e.publisher_group || 'Nguồn verified')}${period}</div></div>`;
    }).join('') : '<div class="evidence-empty">Chưa có evidence verified có thể mở nguồn trực tiếp.</div>';
    const counterHtml=counters.length ? counters.map(e=>{
      const title=esc(e.title || e.interpretation || 'Counter-evidence');
      const link=safe(e.source_url);
      const titleHtml=link!=='#' ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${title}</a>` : title;
      return `<div class="evidence-row counter-row">${titleHtml}${e.interpretation ? `<div class="evidence-meta">${esc(e.interpretation)}</div>` : ''}</div>`;
    }).join('') : '<div class="evidence-empty">Chưa có phản chứng active cho theme này.</div>';
    return `<details class="evidence-drilldown" data-theme="${esc(themeId(t))}">
      <summary>${esc(summary)}</summary>
      <div class="evidence-audit-body">
        <div class="evidence-audit-head">Bằng chứng đang tạo conviction</div>
        ${evidenceHtml}
        <div class="evidence-audit-head">Phản chứng / điều kiện phải thận trọng</div>
        ${counterHtml}
        <div class="evidence-meta" style="margin-top:9px">Verified publishers: ${esc(publishers.join(' · ') || '—')} · Score gốc ${esc(t?.score ?? '—')} · Sau phản chứng ${esc(c?.tension_adjusted_score ?? t?.score ?? '—')}</div>
      </div>
    </details>`;
  }

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
    const source = x.url ? `<a href="${esc(safe(x.url))}" target="_blank" rel="noopener noreferrer">mở nguồn đầu tiên</a>` : '';
    return `<article class="panel attention-card"${x.themeId ? ` data-money-theme="${esc(x.themeId)}"` : ''}>
      <div class="overview-kicker">${esc(x.kind)} · ${esc(x.level)}</div>
      <h3>${esc(x.title)}</h3>
      <p>${esc(x.why)}</p>
      <div class="attention-question"><strong>Câu hỏi tiếp theo:</strong> ${esc(x.question)}</div>
      ${x.auditHtml || ''}
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
      const aa=cMap[themeId(a)]?.tension_adjusted_score ?? a.score ?? 0;
      const bb=cMap[themeId(b)]?.tension_adjusted_score ?? b.score ?? 0;
      return bb-aa;
    }).slice(0,2).forEach(t=>{
      const id=themeId(t);
      const c=cMap[id];
      const adjusted = c?.tension_adjusted_score ?? t.score;
      const verified=verifiedEvidence(t);
      out.push({
        kind:'MONEY FLOW', level:t.status==='converging'?'CONVERGING':'WATCH', title:t.label,
        why:(t.economic_chain||[]).slice(0,2).join(' → ') || `Theme score ${adjusted}`,
        question:'Dòng tiền này đã chuyển thành buyer, CAPEX, hiring hoặc economics quan sát được ở đâu?',
        evidence:`Score sau phản chứng ${adjusted} · ${(t.independent_families||[]).length} evidence families · ${verified.length} verified evidence`,
        url:verified[0]?.source_url,
        themeId:id,
        auditHtml:evidenceDetails(t,c)
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

  function patchMoneyOverview(money, contradiction){
    const cMap=Object.fromEntries((contradiction?.themes || []).map(x=>[x.theme_id,x]));
    const byLabel=Object.fromEntries((money?.themes || []).map(t=>[String(t.label||''),t]));
    const apply=()=>{
      document.querySelectorAll('#moneyFlowOverview .overview-card').forEach(card=>{
        const label=card.querySelector('h3')?.textContent?.trim();
        const t=byLabel[label];
        if(!t) return;
        const c=cMap[themeId(t)];
        const adjusted=c?.tension_adjusted_score ?? t.score;
        const big=card.querySelector('.big-number');
        if(big) big.textContent=String(adjusted ?? '—');
        if(!card.querySelector('.evidence-drilldown')) card.insertAdjacentHTML('beforeend', evidenceDetails(t,c));
      });
    };
    apply();
    const target=document.getElementById('moneyFlowOverview');
    if(target){
      const obs=new MutationObserver(apply);
      obs.observe(target,{childList:true,subtree:true});
      setTimeout(()=>obs.disconnect(),5000);
    }
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

  ensureAuditStyles();
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
    if(grid){
      const rows=buildQueue({policy,money,regional,convergence,corporate,contradiction});
      grid.innerHTML=rows.length?rows.map(attentionCard).join(''):'<div class="panel muted">Chưa có thay đổi nào vượt ngưỡng để đưa vào hàng đợi. Không có alert cũng là một kết quả hợp lệ.</div>';
    }
    patchMoneyOverview(money,contradiction);
  });
})();
