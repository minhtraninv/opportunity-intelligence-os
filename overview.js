(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const safe = (v) => { try { const u = new URL(v); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
  const VERIFIED_QUALITIES = new Set(['official_verified','curated','primary_verified']);

  const GUIDE = {
    manufacturing_expansion: {
      label: 'Dịch vụ B2B quanh cụm sản xuất', capital: '0–5 triệu để test', network: 'Trung bình', difficulty: 'Vừa',
      idea: 'Lead intelligence, tuyển dụng marketing, sourcing theo đơn, research nhà máy/supplier, dịch vụ vận hành có thể productize.',
      avoid: 'Không ôm hàng, thuê xưởng hay cố vào vendor list lớn trước khi có buyer thật.'
    },
    logistics_trade: {
      label: 'Distribution / sourcing / logistics intelligence', capital: '0–10 triệu để test', network: 'Trung bình–cao', difficulty: 'Vừa–khó',
      idea: 'Tìm buyer/supplier, điều phối sourcing, dữ liệu tuyến hàng, lead-gen cho forwarder/kho vận hoặc dịch vụ số hỗ trợ logistics.',
      avoid: 'Không mua xe/kho hay chịu công nợ lớn khi chưa có volume lặp lại.'
    },
    public_infrastructure: {
      label: 'Dịch vụ vòng 2 quanh đầu tư công', capital: '2–20 triệu để test', network: 'Cao', difficulty: 'Khó',
      idea: 'Theo dõi nơi công trường tạo nhu cầu thật rồi tìm dịch vụ nhỏ: data/lead, hậu cần, tuyển dụng, sourcing, dịch vụ địa phương.',
      avoid: 'Không coi gói thầu lớn là cơ hội trực tiếp của cá nhân vốn nhỏ.'
    },
    sme_formalization: {
      label: 'AI-enabled service cho SME/hộ kinh doanh', capital: '0–5 triệu để test', network: 'Thấp–trung bình', difficulty: 'Dễ–vừa',
      idea: 'Automation, reporting, content, sales support, data cleanup, workflow số, lead-gen; bắt đầu bằng service rồi productize.',
      avoid: 'Không nhận dịch vụ pháp lý/kế toán có điều kiện nếu không đủ chuyên môn hoặc giấy phép.'
    },
    data_infrastructure: {
      label: 'Data / automation / research layer', capital: '0–5 triệu để test', network: 'Thấp–trung bình', difficulty: 'Vừa',
      idea: 'Data ops, monitoring, reporting, automation, niche intelligence và công cụ nhỏ cho doanh nghiệp.',
      avoid: 'Không nhảy từ headline AI/data center sang đầu tư phần cứng hoặc CAPEX lớn.'
    },
    energy_grid: {
      label: 'Intelligence và hỗ trợ bán hàng kỹ thuật', capital: '0–5 triệu để test', network: 'Trung bình–cao', difficulty: 'Khó',
      idea: 'Market intelligence, lead research, tender monitoring, sales enablement cho doanh nghiệp kỹ thuật nếu có partner chuyên môn.',
      avoid: 'Không tự cung cấp thiết bị/dịch vụ kỹ thuật đòi hỏi chứng nhận khi chưa đủ năng lực.'
    },
    consumer_services: {
      label: 'Distribution và trải nghiệm ngách', capital: '1–10 triệu để test', network: 'Thấp–trung bình', difficulty: 'Vừa',
      idea: 'Content/distribution, niche experience, digital product, local service có thể test demand trước khi thuê mặt bằng.',
      avoid: 'Không dùng tăng trưởng doanh thu danh nghĩa làm lý do mở cửa hàng hoặc gánh fixed cost.'
    }
  };

  const REGION_STATE = {
    dual_acceleration: 'Vốn + sản xuất cùng tăng',
    production_strong_capital_cooling: 'Sản xuất mạnh, vốn mới hạ nhiệt',
    production_acceleration_capital_unconfirmed: 'Sản xuất tăng, vốn chưa xác nhận',
    capital_acceleration_sector_unconfirmed: 'Vốn tăng, ngành chưa xác nhận',
    capital_positive_production_unconfirmed: 'Vốn dương, sản xuất chưa xác nhận',
    capital_cooling_production_unconfirmed: 'Vốn hạ nhiệt, sản xuất chưa xác nhận'
  };

  const CONVERGENCE_STATE = {
    high_convergence: 'HỘI TỤ CAO · ĐÁNG ĐIỀU TRA',
    converging: 'ĐANG HỘI TỤ · THEO DÕI SÂU',
    discovery_convergence: 'MEDIA CONVERGENCE · CẦN XÁC MINH',
    watch: 'ĐÃ XUẤT HIỆN · CHƯA ĐỦ BẰNG CHỨNG'
  };

  const FAMILY_LABEL = {
    policy: 'Chính sách', capital: 'Dòng vốn / FDI', production: 'Sản xuất', trade: 'Xuất nhập khẩu',
    public_capital: 'Đầu tư công', project_execution: 'Dự án / thực thi', strategy: 'Chiến lược',
    operating: 'Vận hành / demand', labor: 'Lao động', consumption: 'Tiêu dùng', energy: 'Điện / năng lượng',
    business_formation: 'Hình thành DN', procurement: 'Mua sắm công'
  };

  const MACRO_EXPLAIN = {
    production: 'Sản xuất công nghiệp đang mở rộng; cần kiểm tra xem tăng trưởng có lan sang việc làm, điện, logistics và supplier không.',
    labor: 'Việc làm công nghiệp tăng là bằng chứng vận hành tốt hơn headline CAPEX đơn thuần.',
    trade: 'Thương mại tăng mạnh, nhưng nhập khẩu tăng nhanh có thể vừa là đầu vào sản xuất vừa là áp lực cán cân/biên lợi nhuận.',
    consumption: 'Sức mua thực tăng nhưng chậm hơn doanh thu danh nghĩa; tránh đọc quá mạnh câu chuyện tiêu dùng.',
    capital: 'FDI đăng ký tăng nhanh là tín hiệu vốn tương lai; phải đối chiếu FDI thực hiện và thời điểm nhà máy vận hành.',
    public_capital: 'Đầu tư công tạo cầu trực tiếp và vòng 2, nhưng cơ hội cá nhân thường nằm ở dịch vụ/hậu cần chứ không phải gói thầu chính.',
    energy: 'Mức điện là proxy hoạt động kinh tế nhưng một ngày đơn lẻ không phải trend.'
  };

  const themeId = (t) => t?.id || t?.theme_id || '';
  const sourceAnchor = (url, label='Mở nguồn') => {
    const href = safe(url);
    return href === '#' ? '<span class="muted">Không có link nguồn trực tiếp</span>' : `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
  };
  const verifiedEvidence = (t) => (t?.evidence || []).filter(e => e && VERIFIED_QUALITIES.has(e.quality) && e.family !== 'procurement' && e.directional !== false);
  const adjustedScore = (t, cMap) => cMap?.[themeId(t)]?.tension_adjusted_score ?? t?.score ?? 0;

  function evidenceDetails(t, c){
    const verified = verifiedEvidence(t);
    const counters = (c?.counter_signals || []).filter(Boolean);
    const families = t?.verified_evidence_families || t?.independent_families || [];
    const publishers = t?.verified_evidence_publishers || t?.independent_publishers || [];
    const raw = t?.score ?? '—';
    const adjusted = c?.tension_adjusted_score ?? raw;
    const evidenceHtml = verified.length ? verified.map(e => {
      const title = esc(e.title || 'Bằng chứng');
      const href = safe(e.source_url);
      const linked = href === '#' ? title : `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${title}</a>`;
      const meta = [FAMILY_LABEL[e.family] || e.family, e.publisher || e.publisher_group, e.observed_at ? `kỳ ${e.observed_at}` : null, e.snapshot_freshness].filter(Boolean).join(' · ');
      return `<div class="evidence-row">${linked}<div class="evidence-meta">${esc(meta)}</div></div>`;
    }).join('') : '<div class="evidence-empty">Chưa có evidence verified có link trực tiếp.</div>';
    const counterHtml = counters.length ? counters.map(e => {
      const title = esc(e.title || 'Counter-evidence');
      const href = safe(e.source_url);
      const linked = href === '#' ? title : `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${title}</a>`;
      return `<div class="evidence-row counter-row">${linked}${e.interpretation ? `<div class="evidence-meta">${esc(e.interpretation)}</div>` : ''}${e.falsifies_if ? `<div class="evidence-falsify"><strong>Hạ thesis nếu:</strong> ${esc(e.falsifies_if)}</div>` : ''}</div>`;
    }).join('') : '<div class="evidence-empty">Chưa có phản chứng active cho theme này.</div>';
    return `<details class="evidence-drilldown" data-theme="${esc(themeId(t))}">
      <summary>${esc(`${verified.length} bằng chứng verified · ${families.length} họ · ${publishers.length} nguồn độc lập · ${counters.length} phản chứng`)}</summary>
      <div class="evidence-audit-body">
        <div class="evidence-scoreline"><strong>Score:</strong> gốc ${esc(raw)} → sau phản chứng ${esc(adjusted)}${c?.tension_level ? ` · tension ${esc(c.tension_level)}` : ''}</div>
        <div class="evidence-audit-head">Bằng chứng đang tạo conviction</div>${evidenceHtml}
        <div class="evidence-audit-head">Phản chứng / điều kiện phải thận trọng</div>${counterHtml}
        <div class="evidence-meta evidence-publishers">Verified publishers: ${esc(publishers.join(' · ') || '—')}</div>
      </div>
    </details>`;
  }

  function regionDetails(r){
    const iip = r?.evidence?.iip_source_url;
    const fdi = r?.evidence?.fdi_source_url;
    const links = [iip ? sourceAnchor(iip,'Nguồn IIP') : '', fdi ? sourceAnchor(fdi,'Nguồn FDI') : ''].filter(Boolean);
    const proxies = (r?.next_proxies || []).slice(0,5);
    return `<details class="evidence-drilldown"><summary>${esc(`${links.length} nguồn trực tiếp · xem cách xác minh tiếp`)}</summary><div class="evidence-audit-body">
      <div class="evidence-audit-head">Nguồn số liệu</div><div class="evidence-source-links">${links.join(' · ') || '<span class="muted">Chưa có link nguồn trực tiếp.</span>'}</div>
      <div class="evidence-audit-head">Proxy cần kiểm tra trước khi nâng thesis</div>${proxies.length ? `<ul class="overview-list">${proxies.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>` : '<div class="evidence-empty">Chưa định nghĩa proxy tiếp theo.</div>'}
    </div></details>`;
  }

  function entityDetails(e){
    const rows = (e?.evidence || []).slice(0,6);
    return `<details class="evidence-drilldown"><summary>${esc(`${rows.length} evidence gần nhất · mở provenance`)}</summary><div class="evidence-audit-body">
      ${rows.length ? rows.map(x=>{
        const href=safe(x.source_url); const title=esc(x.title || 'Evidence');
        const linked=href==='#'?title:`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${title}</a>`;
        return `<div class="evidence-row">${linked}<div class="evidence-meta">${esc(FAMILY_LABEL[x.family] || x.family || 'Evidence')} · ${esc(x.publisher || x.source_name || '')}</div></div>`;
      }).join('') : '<div class="evidence-empty">Không có evidence công khai để drill-down.</div>'}
    </div></details>`;
  }

  function contradictionDetails(x){
    const rows = (x?.counter_signals || []).filter(Boolean);
    return `<details class="evidence-drilldown"><summary>${esc(`${rows.length} phản chứng verified · xem nguồn và falsifier`)}</summary><div class="evidence-audit-body">
      ${rows.length ? rows.map(e=>{
        const href=safe(e.source_url); const title=esc(e.title || 'Counter-evidence');
        const linked=href==='#'?title:`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${title}</a>`;
        return `<div class="evidence-row counter-row">${linked}${e.interpretation?`<div class="evidence-meta">${esc(e.interpretation)}</div>`:''}${e.falsifies_if?`<div class="evidence-falsify"><strong>Điều kiện hạ thesis:</strong> ${esc(e.falsifies_if)}</div>`:''}</div>`;
      }).join('') : '<div class="evidence-empty">Chưa có phản chứng verified.</div>'}
    </div></details>`;
  }

  window.OIAuditUI = {esc, safe, sourceAnchor, themeId, verifiedEvidence, adjustedScore, evidenceDetails, regionDetails, entityDetails, contradictionDetails, familyLabel:FAMILY_LABEL};

  function fmtPct(v){ return v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${Number(v).toLocaleString('vi-VN')}%`; }
  function fmtMacro(o){
    const v = Number(o.value);
    if(o.unit === 'percent_yoy' || o.unit === 'percent_yoy_real') return `${v > 0 ? '+' : ''}${v.toLocaleString('vi-VN')}%`;
    if(o.unit === 'billion_vnd') return `${Math.round(v).toLocaleString('vi-VN')} tỷ`;
    if(o.unit === 'million_kwh_day') return `${v.toLocaleString('vi-VN')} triệu kWh`;
    return Number.isFinite(v) ? v.toLocaleString('vi-VN') : '—';
  }
  function switchTab(id){ document.querySelector(`.tab[data-tab="${id}"]`)?.click(); }

  function macroCard(o){
    return `<article class="panel overview-card">
      <div class="overview-kicker">MACRO · ${esc(FAMILY_LABEL[o.family] || o.family || 'evidence')}</div>
      <div class="overview-path"><div><div class="big-number">${esc(fmtMacro(o))}</div><div class="muted small">${esc(o.period || '')}</div></div><div><h3>${esc(o.title)}</h3><p class="muted">${esc(MACRO_EXPLAIN[o.family] || o.notes || '')}</p></div></div>
      <div class="card-footer">${sourceAnchor(o.source_url,'Nguồn chính thức')}</div>
    </article>`;
  }

  function policyCard(p){
    return `<article class="panel overview-card overview-policy">
      <div class="overview-kicker">POLICY · RELEVANCE ${esc(p.strategic_relevance ?? '—')}</div><h3>${esc(p.title)}</h3><p>${esc(p.mechanism)}</p>
      <div class="card-footer"><strong>Người bình thường nên hiểu gì?</strong><p class="muted">${esc(p.normal_person_angle)}</p><strong>Cơ chế tạo tài sản:</strong><p class="muted">${esc(p.wealth_mechanism)}</p>${sourceAnchor(p.source_url,'Nguồn chính thức')}</div>
    </article>`;
  }

  function moneyCard(t, cMap){
    const c = cMap?.[themeId(t)];
    const adjusted = c?.tension_adjusted_score ?? t.score;
    const chain = (t.economic_chain || []).slice(0,3);
    const families = t.verified_evidence_families || t.independent_families || [];
    return `<article class="panel overview-card">
      <div class="overview-kicker">MONEY FLOW · ${esc(t.status || 'watch')}</div>
      <div class="overview-path"><div><div class="big-number">${esc(adjusted)}</div><div class="muted small">sau phản chứng</div></div><div><h3>${esc(t.label)}</h3><ul class="overview-list">${chain.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></div>
      <div class="card-footer muted small">Score gốc ${esc(t.score ?? '—')} · ${esc(families.length)} evidence families verified · Supply ${esc(t.supply_gap?.status || 'chưa xác nhận')}</div>
      ${evidenceDetails(t,c)}
    </article>`;
  }

  function regionCard(r){
    return `<article class="panel overview-card">
      <div class="overview-kicker">REGIONAL FLOW · PRIORITY ${esc(r.priority_score ?? '—')}</div><h3>${esc(r.region)}</h3><div class="overview-state">${esc(REGION_STATE[r.state] || r.state)}</div>
      <div class="overview-path-metrics"><span class="pill">IIP ${esc(fmtPct(r.iip_7m_yoy_pct))}</span><span class="pill">FDI YoY ${esc(fmtPct(r.fdi_yoy_pct))}</span></div><p class="muted small">${esc(r.interpretation || '')}</p>${regionDetails(r)}
    </article>`;
  }

  function entityCard(e){
    const families = (e.evidence_families || []).map(x=>FAMILY_LABEL[x] || x);
    const themes = (e.theme_context || []).map(x=>x.label).slice(0,3);
    const regions = (e.regional_context || []).map(x=>x.region).slice(0,3);
    const primary = Number(e.primary_evidence_count || 0);
    const media = Number(e.media_evidence_count || 0);
    return `<article class="panel overview-card ${e.status === 'high_convergence' ? 'overview-policy' : ''}">
      <div class="overview-kicker">${esc(CONVERGENCE_STATE[e.status] || e.status)} · SCORE ${esc(e.convergence_score)}</div><h3>${esc(e.label)}</h3><p>${esc(e.why_now)}</p>
      <div class="overview-path-metrics">${families.map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>
      <p class="muted small">Primary ${esc(primary)} · Media discovery ${esc(media)}${(themes.length || regions.length) ? ` · Bối cảnh: ${esc([...themes,...regions].join(' · '))}` : ''}</p>${entityDetails(e)}
    </article>`;
  }

  function opportunityCard(t, cMap){
    const id = themeId(t); const g = GUIDE[id]; if(!g) return '';
    const c = cMap?.[id]; const adjusted = c?.tension_adjusted_score ?? t.score;
    return `<article class="panel overview-card overview-opportunity">
      <div class="overview-kicker">HYPOTHESIS ENTRY · UPSTREAM ${esc(t.status || 'watch')}</div><h3>${esc(g.label)}</h3><p>${esc(g.idea)}</p>
      <div class="overview-path-metrics"><span class="pill">Vốn: ${esc(g.capital)}</span><span class="pill">Network: ${esc(g.network)}</span><span class="pill">Độ khó: ${esc(g.difficulty)}</span><span class="pill">Theme score ${esc(adjusted)}</span></div>
      <div class="card-footer"><strong>Không nên làm:</strong> <span class="muted">${esc(g.avoid)}</span><div class="muted small" style="margin-top:7px">Đây là hypothesis được suy ra từ theme “${esc(t.label)}”, không phải fact hay khuyến nghị.</div></div>${evidenceDetails(t,c)}
    </article>`;
  }

  function contradictionCard(x){
    const first = (x.counter_signals || [])[0];
    return `<article class="panel overview-card overview-warning">
      <div class="overview-kicker">WHAT COULD BE WRONG? · ${esc(x.tension_level || 'watch')}</div><h3>${esc(x.theme_label)}</h3><p><strong>${esc(first?.title || 'Chưa có phản chứng xác minh')}</strong></p><p class="muted">${esc(first?.interpretation || 'Thiếu phản chứng không đồng nghĩa thesis đúng.')}</p>${contradictionDetails(x)}
    </article>`;
  }

  document.querySelectorAll('[data-overview-tab]').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.overviewTab)));

  Promise.all([
    fetch('data/macro_observations.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/policy_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/money_flow_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/regional_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/entity_convergence_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/contradiction_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/thesis_lifecycle.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)
  ]).then(([macro, policy, money, regional, convergence, contradiction, lifecycle]) => {
    const macroRows = macro?.observations || [];
    const pRows = policy?.structural_policies || [];
    const cRows = contradiction?.themes || [];
    const cMap = Object.fromEntries(cRows.map(x=>[x.theme_id,x]));
    const themes = (money?.themes || []).slice().sort((a,b)=>adjustedScore(b,cMap)-adjustedScore(a,cMap));
    const regions = (regional?.regions || []).slice().sort((a,b)=>(b.priority_score||0)-(a.priority_score||0)).slice(0,6);
    const entities = (convergence?.entities || []).slice();
    const lCov = lifecycle?.coverage || {};
    const eCov = convergence?.coverage || {};

    const heroTitle = document.getElementById('overviewHeroTitle');
    const heroText = document.getElementById('overviewHeroText');
    if(heroTitle) heroTitle.textContent = 'Nhìn bức tranh lớn trước khi nghĩ tới một kèo cụ thể.';
    if(heroText) heroText.textContent = policy?.thesis || money?.thesis || 'Đang dựng bối cảnh.';

    const pulse = document.getElementById('overviewPulse');
    if(pulse) pulse.innerHTML = `
      <div class="overview-pulse-item"><span class="muted small">Macro verified</span><strong>${esc(macroRows.length)} số liệu gốc</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Policy structural</span><strong>${esc(pRows.length)} thay đổi lớn</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Money-flow themes</span><strong>${esc(themes.length)} theme theo dõi</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Regional radar</span><strong>${esc(regions.length)} địa bàn nổi bật</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Verified entities</span><strong>${esc(eCov.public_verified_entities ?? entities.length)} entity</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Lifecycle</span><strong>${lCov.directional_lifecycle_active ? 'Đã đủ lịch sử xu hướng' : `${esc(lCov.max_observation_days ?? 0)}/3 ngày học`}</strong></div>`;

    const macroGrid = document.getElementById('macroOverview');
    if(macroGrid) macroGrid.innerHTML = macroRows.slice(0,6).map(macroCard).join('') || '<div class="panel muted">Chưa có macro observations.</div>';

    const policyGrid = document.getElementById('policyOverview');
    if(policyGrid) policyGrid.innerHTML = pRows.slice(0,4).map(policyCard).join('') || '<div class="panel muted">Chưa có Policy Radar.</div>';

    const moneyGrid = document.getElementById('moneyFlowOverview');
    if(moneyGrid) moneyGrid.innerHTML = themes.slice(0,4).map(t=>moneyCard(t,cMap)).join('') || '<div class="panel muted">Chưa có Money Flow.</div>';

    const regionGrid = document.getElementById('regionalOverview');
    if(regionGrid) regionGrid.innerHTML = regions.slice(0,4).map(regionCard).join('') || '<div class="panel muted">Chưa có Regional Radar.</div>';

    const entityGrid = document.getElementById('entityConvergenceOverview');
    if(entityGrid){
      const visible = entities.filter(x=>x.status !== 'not_observed').slice(0,6);
      entityGrid.innerHTML = visible.map(entityCard).join('') || '<div class="panel muted">Chưa có entity nào vượt primary-evidence gate. Đây là kết quả hợp lệ: hệ thống không ép phải có “câu chuyện”.</div>';
    }

    const opportunityGrid = document.getElementById('normalPersonOverview');
    if(opportunityGrid){
      const eligible = themes.filter(t=>GUIDE[themeId(t)]).slice(0,4);
      opportunityGrid.innerHTML = eligible.map(t=>opportunityCard(t,cMap)).join('') || '<div class="panel muted">Chưa có theme đủ rõ để dịch thành cửa vào vốn nhỏ.</div>';
    }

    const wealthGrid = document.getElementById('wealthMechanismOverview');
    if(wealthGrid){
      wealthGrid.innerHTML = pRows.slice(0,4).map(p=>`<article class="panel overview-card"><div class="overview-kicker">HYPOTHESIS · DERIVED FROM POLICY</div><h3>${esc(p.title)}</h3><p>${esc(p.wealth_mechanism)}</p><div class="card-footer"><span class="muted small">Cơ chế suy luận, không phải dự báo chắc chắn.</span> · ${sourceAnchor(p.source_url,'Nguồn policy')}</div></article>`).join('') || '<div class="panel muted">Chưa có cơ chế tài sản để theo dõi.</div>';
    }

    const realityGrid = document.getElementById('realityOverview');
    if(realityGrid) realityGrid.innerHTML = cRows.filter(x=>x.counter_signal_count>0).slice(0,4).map(contradictionCard).join('') || '<div class="panel muted">Chưa có phản chứng xác minh.</div>';

    const lifecycleNote = document.getElementById('overviewLifecycleNote');
    if(lifecycleNote) lifecycleNote.textContent = lifecycle?.thesis || 'Lifecycle chưa có dữ liệu.';
  });
})();