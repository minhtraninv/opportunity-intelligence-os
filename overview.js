(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const safe = (v) => { try { const u = new URL(v); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };

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
    capital_acceleration_sector_unconfirmed: 'Vốn tăng, ngành chưa xác nhận'
  };

  function fmtPct(v){ return v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${Number(v).toLocaleString('vi-VN')}%`; }
  function switchTab(id){
    const btn = document.querySelector(`.tab[data-tab="${id}"]`);
    if(btn) btn.click();
  }

  function policyCard(p){
    return `<article class="panel overview-card overview-policy">
      <div class="overview-kicker">POLICY · RELEVANCE ${esc(p.strategic_relevance ?? '—')}</div>
      <h3>${esc(p.title)}</h3>
      <p>${esc(p.mechanism)}</p>
      <div class="card-footer">
        <strong>Người bình thường nên hiểu gì?</strong>
        <p class="muted">${esc(p.normal_person_angle)}</p>
        <strong>Cơ chế tạo tài sản:</strong>
        <p class="muted">${esc(p.wealth_mechanism)}</p>
        <a href="${esc(safe(p.source_url))}" target="_blank" rel="noopener noreferrer">Nguồn chính thức</a>
      </div>
    </article>`;
  }

  function moneyCard(t, contradiction){
    const c = contradiction?.[t.theme_id];
    const adjusted = c?.tension_adjusted_score ?? t.score;
    const chain = (t.economic_chain || []).slice(0,3);
    return `<article class="panel overview-card">
      <div class="overview-kicker">MONEY FLOW · ${esc(t.status || 'watch')}</div>
      <div class="overview-path">
        <div><div class="big-number">${esc(adjusted)}</div><div class="muted small">sau phản chứng</div></div>
        <div>
          <h3>${esc(t.label)}</h3>
          <ul class="overview-list">${chain.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
        </div>
      </div>
      <div class="card-footer muted small">Supply: ${esc(t.supply_gap?.status || 'chưa xác nhận')} · Evidence families: ${esc((t.independent_families||[]).length)}</div>
    </article>`;
  }

  function regionCard(r){
    return `<article class="panel overview-card">
      <div class="overview-kicker">REGIONAL FLOW</div>
      <h3>${esc(r.region)}</h3>
      <div class="overview-state">${esc(REGION_STATE[r.state] || r.state)}</div>
      <div class="overview-path-metrics">
        <span class="pill">IIP ${esc(fmtPct(r.iip_7m_yoy_pct))}</span>
        <span class="pill">FDI YoY ${esc(fmtPct(r.fdi_yoy_pct))}</span>
      </div>
      <p class="muted small">${esc(r.interpretation || '')}</p>
    </article>`;
  }

  function opportunityCard(t){
    const g = GUIDE[t.theme_id];
    if(!g) return '';
    return `<article class="panel overview-card overview-opportunity">
      <div class="overview-kicker">CỬA VÀO CHO NGƯỜI BÌNH THƯỜNG</div>
      <h3>${esc(g.label)}</h3>
      <p>${esc(g.idea)}</p>
      <div class="overview-path-metrics">
        <span class="pill">Vốn: ${esc(g.capital)}</span>
        <span class="pill">Network: ${esc(g.network)}</span>
        <span class="pill">Độ khó: ${esc(g.difficulty)}</span>
      </div>
      <div class="card-footer"><strong>Không nên làm:</strong> <span class="muted">${esc(g.avoid)}</span></div>
    </article>`;
  }

  function contradictionCard(x){
    const first = (x.counter_signals || [])[0];
    return `<article class="panel overview-card overview-warning">
      <div class="overview-kicker">WHAT COULD BE WRONG?</div>
      <h3>${esc(x.theme_label)}</h3>
      <p><strong>${esc(first?.title || 'Chưa có phản chứng xác minh')}</strong></p>
      <p class="muted">${esc(first?.interpretation || 'Thiếu phản chứng không đồng nghĩa thesis đúng.')}</p>
    </article>`;
  }

  Promise.all([
    fetch('data/policy_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/money_flow_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/regional_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/contradiction_intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('data/thesis_lifecycle.json', {cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)
  ]).then(([policy, money, regional, contradiction, lifecycle]) => {
    const pRows = policy?.structural_policies || [];
    const themes = (money?.themes || []).slice().sort((a,b)=>b.score-a.score);
    const regions = (regional?.regions || []).slice(0,6);
    const cRows = contradiction?.themes || [];
    const cMap = Object.fromEntries(cRows.map(x=>[x.theme_id,x]));
    const lCov = lifecycle?.coverage || {};

    const heroTitle = document.getElementById('overviewHeroTitle');
    const heroText = document.getElementById('overviewHeroText');
    if(heroTitle) heroTitle.textContent = 'Nhìn bức tranh lớn trước khi nghĩ tới một kèo cụ thể.';
    if(heroText) heroText.textContent = policy?.thesis || money?.thesis || 'Đang dựng bối cảnh.';

    const pulse = document.getElementById('overviewPulse');
    if(pulse) pulse.innerHTML = `
      <div class="overview-pulse-item"><span class="muted small">Policy structural</span><strong>${esc(pRows.length)} thay đổi lớn</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Money-flow themes</span><strong>${esc(themes.length)} theme đang theo dõi</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Regional radar</span><strong>${esc(regions.length)} địa bàn nổi bật</strong></div>
      <div class="overview-pulse-item"><span class="muted small">Lifecycle</span><strong>${lCov.directional_lifecycle_active ? 'Đã đủ lịch sử xu hướng' : `${esc(lCov.max_observation_days ?? 0)}/3 ngày học`}</strong></div>`;

    const policyGrid = document.getElementById('policyOverview');
    if(policyGrid) policyGrid.innerHTML = pRows.slice(0,4).map(policyCard).join('') || '<div class="panel muted">Chưa có Policy Radar.</div>';

    const moneyGrid = document.getElementById('moneyFlowOverview');
    if(moneyGrid) moneyGrid.innerHTML = themes.slice(0,4).map(t=>moneyCard(t,cMap)).join('') || '<div class="panel muted">Chưa có Money Flow.</div>';

    const regionGrid = document.getElementById('regionalOverview');
    if(regionGrid) regionGrid.innerHTML = regions.slice(0,4).map(regionCard).join('') || '<div class="panel muted">Chưa có Regional Radar.</div>';

    const opportunityGrid = document.getElementById('normalPersonOverview');
    if(opportunityGrid){
      const eligible = themes.filter(t=>GUIDE[t.theme_id]).slice(0,4);
      opportunityGrid.innerHTML = eligible.map(opportunityCard).join('') || '<div class="panel muted">Chưa có theme đủ rõ để dịch thành cửa vào vốn nhỏ.</div>';
    }

    const wealthGrid = document.getElementById('wealthMechanismOverview');
    if(wealthGrid){
      const rows = pRows.slice(0,4).map(p=>`<article class="panel overview-card"><div class="overview-kicker">HOW VALUE MAY SHIFT</div><h3>${esc(p.title)}</h3><p>${esc(p.wealth_mechanism)}</p></article>`);
      wealthGrid.innerHTML = rows.join('') || '<div class="panel muted">Chưa có cơ chế tài sản để theo dõi.</div>';
    }

    const realityGrid = document.getElementById('realityOverview');
    if(realityGrid) realityGrid.innerHTML = cRows.filter(x=>x.counter_signal_count>0).slice(0,3).map(contradictionCard).join('') || '<div class="panel muted">Chưa có phản chứng xác minh.</div>';

    const lifecycleNote = document.getElementById('overviewLifecycleNote');
    if(lifecycleNote) lifecycleNote.textContent = lifecycle?.thesis || 'Lifecycle chưa có dữ liệu.';

    document.querySelectorAll('[data-overview-tab]').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.overviewTab)));
  });
})();
