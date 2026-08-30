(() => {
  const EXECUTION_KEY = 'oi.execution.v2';
  const PROFILE_KEY = 'oi.personalEdge.v1';
  const STAGES = [
    ['ready_to_research', 'Sẵn sàng'],
    ['contacted', 'Đã liên hệ'],
    ['replied', 'Có phản hồi'],
    ['qualified', 'Qualified'],
    ['dead', 'Dead'],
  ];

  const CATEGORY_WEIGHTS = {
    digital_services: {data_ops:3, software:3, it_delivery:3, project_coordination:2, b2b_sales:2, sourcing:1},
    office_goods: {sourcing:3, b2b_sales:2, logistics:1, project_coordination:1},
    printing_media: {design_media:3, sourcing:2, b2b_sales:2, project_coordination:1},
    maintenance: {facility:3, sourcing:2, project_coordination:2, b2b_sales:1},
    garment_ppe: {sourcing:3, b2b_sales:2, logistics:1},
    food_services: {food_ops:3, sourcing:2, logistics:1, b2b_sales:1},
    logistics: {logistics:3, b2b_sales:2, project_coordination:1, sourcing:1},
    consulting: {consulting:3, project_coordination:2, b2b_sales:1},
    medical: {regulated_goods:3, sourcing:2, technical_sales:2, b2b_sales:1},
    machinery: {technical_sales:3, sourcing:2, it_delivery:1, b2b_sales:1},
    construction: {construction:3, project_coordination:2, sourcing:1},
    other: {b2b_sales:2, sourcing:2, project_coordination:1},
  };

  const CAPABILITY_LABELS = {
    b2b_sales: 'Sales B2B / cold outreach',
    sourcing: 'Tìm nguồn / kết nối supplier',
    project_coordination: 'Điều phối dự án / vendor',
    data_ops: 'Nhập liệu / scan / OCR / QC dữ liệu',
    software: 'Phần mềm / tích hợp / automation',
    it_delivery: 'Triển khai CNTT / thiết bị / hỗ trợ kỹ thuật',
    design_media: 'Thiết kế / nội dung / in ấn',
    food_ops: 'F&B / suất ăn / vận hành thực phẩm',
    logistics: 'Logistics / giao nhận / vận chuyển',
    facility: 'Vệ sinh / facility / bảo trì',
    technical_sales: 'Bán hàng kỹ thuật / máy móc',
    consulting: 'Tư vấn / nghiên cứu / tài liệu',
    construction: 'Thi công / xây dựng / thầu phụ',
    regulated_goods: 'Hàng hóa cần pháp lý / y tế / chứng nhận',
  };

  const CLASS_LABELS = {
    can_execute_now: 'CAN EXECUTE NOW',
    partner_required: 'PARTNER REQUIRED',
    not_for_you: 'NOT FOR YOU',
    profile_needed: 'PROFILE NEEDED',
  };

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const safeUrl = (value) => {
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) ? url.href : '#';
    } catch { return '#'; }
  };

  function readJson(key, fallback={}){
    try { return JSON.parse(localStorage.getItem(key) || '') || fallback; }
    catch { return fallback; }
  }

  function writeJson(key, value){
    localStorage.setItem(key, JSON.stringify(value));
  }

  function loadExecution(){ return readJson(EXECUTION_KEY, {}); }
  function saveExecution(value){ writeJson(EXECUTION_KEY, value); }
  function loadProfile(){ return readJson(PROFILE_KEY, {}); }
  function saveProfile(value){ writeJson(PROFILE_KEY, value); }

  function profileComplete(profile){
    return profile
      && profile.testCapitalM !== undefined && profile.testCapitalM !== null && profile.testCapitalM !== ''
      && profile.weeklyHours !== undefined && profile.weeklyHours !== null && profile.weeklyHours !== ''
      && profile.salesComfort !== undefined && profile.salesComfort !== null && profile.salesComfort !== ''
      && Array.isArray(profile.capabilities) && profile.capabilities.length > 0;
  }

  function enrichedWeights(pack){
    const weights = {...(CATEGORY_WEIGHTS[pack.category] || CATEGORY_WEIGHTS.other)};
    const text = `${pack.category_label || ''} ${pack.offer_to_validate || ''}`.toLowerCase();
    const bump = (id, n=3) => { weights[id] = Math.max(weights[id] || 0, n); };
    if(/ocr|scan|nhập liệu|qc dữ liệu|số hóa/.test(text)) bump('data_ops', 3);
    if(/phần mềm|software|automation|tích hợp|migration/.test(text)) { bump('software', 3); bump('it_delivery', 2); }
    if(/thiết bị|máy móc|hardware/.test(text)) { bump('sourcing', 3); bump('technical_sales', 2); }
    if(/in ấn|truyền thông|thiết kế/.test(text)) bump('design_media', 3);
    if(/vệ sinh|bảo trì|facility/.test(text)) bump('facility', 3);
    if(/vận chuyển|logistics|giao nhận/.test(text)) bump('logistics', 3);
    if(/tư vấn|khảo sát|báo cáo/.test(text)) bump('consulting', 3);
    if(/suất ăn|thực phẩm|food/.test(text)) bump('food_ops', 3);
    return weights;
  }

  function matchPack(pack, profile){
    if(!profileComplete(profile)){
      return {classification:'profile_needed', personalFit:null, capabilityScore:null, reasons:['Hoàn thành Personal Edge để chấm fit cá nhân.']};
    }

    const selected = new Set(profile.capabilities || []);
    const weights = enrichedWeights(pack);
    let weighted = 0;
    let maxWeighted = 0;
    let coreHits = 0;
    let supportHits = 0;
    const matched = [];
    const missingCore = [];

    Object.entries(weights).forEach(([id, weight]) => {
      maxWeighted += weight;
      if(selected.has(id)){
        weighted += weight;
        supportHits += 1;
        if(weight >= 3) coreHits += 1;
        matched.push(CAPABILITY_LABELS[id] || id);
      } else if(weight >= 3){
        missingCore.push(CAPABILITY_LABELS[id] || id);
      }
    });

    const rawCapability = maxWeighted ? Math.round((weighted / maxWeighted) * 100) : 0;
    const capabilityScore = Math.min(100, rawCapability + coreHits * 12);
    const weeklyHours = Number(profile.weeklyHours || 0);
    const testCapital = Number(profile.testCapitalM || 0);
    const salesComfort = Number(profile.salesComfort || 0);
    const timeScore = Math.min(100, weeklyHours * 10);
    const capitalScore = Math.min(100, 35 + testCapital * 8);
    const salesScore = Math.min(100, [20, 50, 75, 100][salesComfort] || 20 + (selected.has('b2b_sales') ? 20 : 0));
    const partnerBoost = profile.partnerOpen ? 10 : 0;
    const personalFit = Math.min(100, Math.round(
      capabilityScore * 0.52 + salesScore * 0.20 + timeScore * 0.14 + capitalScore * 0.09 + partnerBoost * 0.05
    ));

    let classification = 'not_for_you';
    if(coreHits >= 1 && capabilityScore >= 52 && weeklyHours >= 4 && (salesComfort >= 1 || selected.has('b2b_sales'))){
      classification = 'can_execute_now';
    } else if(profile.partnerOpen && (capabilityScore >= 22 || supportHits >= 1)){
      classification = 'partner_required';
    }

    const reasons = [];
    if(matched.length) reasons.push(`Khớp: ${matched.slice(0,3).join(' · ')}`);
    if(missingCore.length) reasons.push(`Thiếu core: ${missingCore.slice(0,2).join(' · ')}`);
    if(weeklyHours < 4) reasons.push('Thời gian hiện tại < 4 giờ/tuần.');
    if(salesComfort === 0 && !selected.has('b2b_sales')) reasons.push('Cold outreach đang là điểm nghẽn.');
    if(classification === 'partner_required') reasons.push('Nên tìm partner trước khi chào năng lực như thể tự thực hiện.');
    if(classification === 'not_for_you') reasons.push('Không nên bỏ thời gian/vốn chỉ vì market signal đang nóng.');

    return {classification, personalFit, capabilityScore, reasons, matched, missingCore};
  }

  function combinedScore(pack, profile){
    const match = matchPack(pack, profile);
    if(match.personalFit == null) return Number(pack.priority_score || 0);
    return Math.round(match.personalFit * 0.62 + Number(pack.priority_score || 0) * 0.38);
  }

  function contactHtml(paths){
    return (paths || []).map(x => `
      <div class="muted small" style="margin-top:4px">
        <strong>${esc(x.type || 'contact')}:</strong> ${esc(x.value)}
        ${x.scope ? ` · ${esc(x.scope)}` : ''}
        ${x.source_url ? ` · <a href="${esc(safeUrl(x.source_url))}" target="_blank" rel="noopener noreferrer">nguồn</a>` : ''}
      </div>`).join('');
  }

  function ensureEdgeTab(){
    if(document.getElementById('edge')) return;
    const nav = document.querySelector('.tabs');
    const buyersTab = nav?.querySelector('[data-tab="buyers"]');
    if(nav && !nav.querySelector('[data-tab="edge"]')){
      const btn = document.createElement('button');
      btn.className = 'tab';
      btn.dataset.tab = 'edge';
      btn.textContent = 'My Edge';
      nav.insertBefore(btn, buyersTab || null);
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === btn));
        document.querySelectorAll('.tab-view').forEach(x => x.classList.toggle('active', x.id === 'edge'));
        window.scrollTo({top:0, behavior:'smooth'});
      });
    }

    const buyers = document.getElementById('buyers');
    if(!buyers) return;
    const section = document.createElement('section');
    section.id = 'edge';
    section.className = 'tab-view';
    section.innerHTML = `
      <div class="section-head">
        <div><div class="eyebrow">PERSONAL EDGE · V1.7</div><h2>Cơ hội nào thực sự phù hợp với năng lực của bạn?</h2></div>
        <span id="edgeStatus" class="muted">Profile chỉ lưu trên trình duyệt này.</span>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <strong>Privacy by design:</strong> vốn, thời gian, kỹ năng và ghi chú ở đây chỉ nằm trong <code>localStorage</code> của trình duyệt. Không gửi lên GitHub, GitHub Actions hay file JSON public. <strong>Nếu dùng cửa sổ ẩn danh, dữ liệu sẽ mất khi đóng cửa sổ.</strong>
      </div>
      <div class="validation-layout">
        <article class="panel">
          <div class="eyebrow">YOUR EXECUTION PROFILE</div>
          <h2>Hồ sơ khả năng thực thi</h2>
          <div id="edgeForm"></div>
        </article>
        <article class="panel">
          <div class="eyebrow">PERSONALIZED CAMPAIGNS</div>
          <h2>Campaign theo fit cá nhân</h2>
          <div id="edgeMatches" class="opportunity-list"></div>
        </article>
      </div>`;
    buyers.parentNode.insertBefore(section, buyers);
  }

  function formHtml(profile){
    const caps = new Set(profile.capabilities || []);
    const val = (x) => x === undefined || x === null ? '' : x;
    return `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">
        <label>Vốn tối đa cho 1 test (triệu)
          <input id="edgeCapital" type="number" min="0" step="1" value="${esc(val(profile.testCapitalM))}" placeholder="VD: 5" />
        </label>
        <label>Thời gian/tuần (giờ)
          <input id="edgeHours" type="number" min="0" step="1" value="${esc(val(profile.weeklyHours))}" placeholder="VD: 8" />
        </label>
        <label>Mức thoải mái với cold outreach
          <select id="edgeSales">
            <option value="" ${val(profile.salesComfort)===''?'selected':''}>Chưa chọn</option>
            <option value="0" ${Number(profile.salesComfort)===0?'selected':''}>0 · Không muốn sales</option>
            <option value="1" ${Number(profile.salesComfort)===1?'selected':''}>1 · Có thể thử</option>
            <option value="2" ${Number(profile.salesComfort)===2?'selected':''}>2 · Khá thoải mái</option>
            <option value="3" ${Number(profile.salesComfort)===3?'selected':''}>3 · Chủ động sales</option>
          </select>
        </label>
        <label>Mục tiêu có tín hiệu doanh thu
          <select id="edgeRevenueDays">
            <option value="14" ${Number(profile.revenueTargetDays)===14?'selected':''}>≤ 2 tuần</option>
            <option value="30" ${!profile.revenueTargetDays || Number(profile.revenueTargetDays)===30?'selected':''}>≤ 1 tháng</option>
            <option value="90" ${Number(profile.revenueTargetDays)===90?'selected':''}>≤ 3 tháng</option>
          </select>
        </label>
        <label>Khả năng di chuyển
          <select id="edgeTravel">
            <option value="remote" ${profile.travel==='remote'?'selected':''}>Ưu tiên online/remote</option>
            <option value="local" ${!profile.travel || profile.travel==='local'?'selected':''}>Trong khu vực đang sống</option>
            <option value="regional" ${profile.travel==='regional'?'selected':''}>Có thể đi tỉnh lân cận</option>
            <option value="national" ${profile.travel==='national'?'selected':''}>Có thể đi toàn quốc</option>
          </select>
        </label>
        <label>Chấp nhận ôm hàng/tồn kho
          <select id="edgeInventory">
            <option value="none" ${!profile.inventoryTolerance || profile.inventoryTolerance==='none'?'selected':''}>Không / rất ít</option>
            <option value="low" ${profile.inventoryTolerance==='low'?'selected':''}>Thấp</option>
            <option value="medium" ${profile.inventoryTolerance==='medium'?'selected':''}>Vừa</option>
          </select>
        </label>
      </div>

      <div style="margin-top:16px;font-weight:700">Năng lực bạn thực sự có thể dùng ngay</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin-top:8px">
        ${Object.entries(CAPABILITY_LABELS).map(([id,label]) => `<label style="display:flex;gap:8px;align-items:flex-start"><input class="edge-cap" type="checkbox" value="${id}" ${caps.has(id)?'checked':''}> <span>${esc(label)}</span></label>`).join('')}
      </div>

      <label style="display:flex;gap:8px;align-items:center;margin-top:14px"><input id="edgePartner" type="checkbox" ${profile.partnerOpen!==false?'checked':''}> Sẵn sàng tìm partner để bù năng lực thiếu</label>
      <label style="display:block;margin-top:12px">Tài sản / network / lợi thế khác (tùy chọn)
        <textarea id="edgeNotes" rows="3" placeholder="Ví dụ: có máy tính mạnh, có cửa hàng, quen supplier, từng vận hành nhóm nhỏ…">${esc(profile.notes || '')}</textarea>
      </label>
      <div class="button-row" style="margin-top:12px">
        <button id="edgeSave" class="btn primary">Lưu profile trên máy này</button>
        <button id="edgeClear" class="btn ghost">Xóa profile</button>
      </div>
      <p id="edgeMessage" class="muted small" style="margin-top:8px"></p>`;
  }

  function collectProfile(){
    return {
      testCapitalM: document.getElementById('edgeCapital')?.value === '' ? null : Number(document.getElementById('edgeCapital')?.value),
      weeklyHours: document.getElementById('edgeHours')?.value === '' ? null : Number(document.getElementById('edgeHours')?.value),
      salesComfort: document.getElementById('edgeSales')?.value === '' ? null : Number(document.getElementById('edgeSales')?.value),
      revenueTargetDays: Number(document.getElementById('edgeRevenueDays')?.value || 30),
      travel: document.getElementById('edgeTravel')?.value || 'local',
      inventoryTolerance: document.getElementById('edgeInventory')?.value || 'none',
      partnerOpen: Boolean(document.getElementById('edgePartner')?.checked),
      capabilities: [...document.querySelectorAll('.edge-cap:checked')].map(x => x.value),
      notes: document.getElementById('edgeNotes')?.value || '',
      updatedAt: new Date().toISOString(),
    };
  }

  function edgeMatchCard(pack, profile){
    const m = matchPack(pack, profile);
    const personal = m.personalFit == null ? '—' : m.personalFit;
    const combined = m.personalFit == null ? '—' : combinedScore(pack, profile);
    return `<article class="opp-card">
      <div class="opp-scorebox"><div class="opp-score ${m.personalFit >= 70 ? 'good' : m.personalFit >= 45 ? 'mid' : 'low'}">${esc(personal)}</div><div class="opp-label">PERSONAL FIT</div></div>
      <div class="opp-main">
        <h3>${esc(pack.contractor_name)}</h3>
        <p><strong>${esc(CLASS_LABELS[m.classification])}</strong> · ${esc(pack.category_label || pack.category)}</p>
        <div class="opp-tags">
          <span class="pill">Market ${esc(pack.priority_score)}/100</span>
          <span class="pill">Combined ${esc(combined)}</span>
          <span class="pill">${esc(pack.related_opportunity_count || 0)} market signals</span>
        </div>
        <div class="risk"><strong>Vì sao:</strong> ${esc(m.reasons.join(' '))}</div>
      </div>
    </article>`;
  }

  function renderEdge(packs){
    ensureEdgeTab();
    const profile = loadProfile();
    const form = document.getElementById('edgeForm');
    if(form) form.innerHTML = formHtml(profile);

    const matches = document.getElementById('edgeMatches');
    const sorted = [...packs].sort((a,b) => combinedScore(b, profile) - combinedScore(a, profile));
    if(matches){
      matches.innerHTML = sorted.length
        ? sorted.map(x => edgeMatchCard(x, profile)).join('')
        : '<div class="muted">Chưa có campaign đủ evidence gates.</div>';
    }

    const status = document.getElementById('edgeStatus');
    if(status){
      const complete = profileComplete(profile);
      const counts = sorted.reduce((acc,p) => {
        const c = matchPack(p, profile).classification;
        acc[c] = (acc[c] || 0) + 1;
        return acc;
      }, {});
      status.textContent = complete
        ? `${counts.can_execute_now || 0} execute now · ${counts.partner_required || 0} partner required · ${counts.not_for_you || 0} not for you`
        : 'Chưa đủ profile để chấm fit cá nhân.';
    }

    document.getElementById('edgeSave')?.addEventListener('click', () => {
      const next = collectProfile();
      saveProfile(next);
      renderEdge(packs);
      renderExecution(packs);
      const msg = document.getElementById('edgeMessage');
      if(msg) msg.textContent = 'Đã lưu cục bộ trên trình duyệt này. Không upload lên GitHub.';
    });
    document.getElementById('edgeClear')?.addEventListener('click', () => {
      localStorage.removeItem(PROFILE_KEY);
      renderEdge(packs);
      renderExecution(packs);
    });
  }

  function ensureExecutionSection(){
    let grid = document.getElementById('executionQueue');
    if(grid) return grid;
    const actionQueue = document.getElementById('actionQueue');
    const hero = document.querySelector('#today .hero-grid');
    const anchor = actionQueue || hero;
    if(!anchor) return null;
    const html = `
      <div id="executionQueueHead" class="section-head" style="margin-top:28px">
        <div><div class="eyebrow">EXECUTION LOOP · V1.7</div><h2>Campaign đã đủ bằng chứng để điều tra</h2></div>
        <span id="executionQueueStatus" class="muted">Đang dựng campaign queue…</span>
      </div>
      <div class="panel" style="margin-bottom:14px">
        <strong>Human-in-the-loop:</strong> một counterparty + một nhóm năng lực chỉ là một campaign dù có nhiều tender signals. Nếu Personal Edge đã hoàn thành, queue ưu tiên theo fit cá nhân. Draft chỉ được copy khi có bằng chứng năng lực thật.
      </div>
      <div id="executionQueue" class="signal-grid"></div>`;
    anchor.insertAdjacentHTML('afterend', html);
    return document.getElementById('executionQueue');
  }

  function relatedSignalsHtml(pack){
    const rows = (pack.related_opportunities || []).slice(0,4);
    if(!rows.length) return '';
    return `<details style="margin-top:10px"><summary style="cursor:pointer;font-weight:700">${esc(pack.related_opportunity_count || rows.length)} tender signals đang được gom vào campaign</summary>
      <ul>${rows.map(x => `<li><strong>${esc(x.tender_code)}</strong> · ${esc(x.buyer)} · ${esc(x.title)}</li>`).join('')}</ul>
    </details>`;
  }

  function packCard(pack, executionState, profile){
    const local = executionState[pack.id] || {};
    const stage = local.stage || pack.default_stage || 'ready_to_research';
    const proof = local.capabilityProof || '';
    const note = local.note || '';
    const historical = pack.historical_evidence || {};
    const m = matchPack(pack, profile);
    const fitText = m.personalFit == null ? 'Profile chưa đủ' : `${CLASS_LABELS[m.classification]} · Personal fit ${m.personalFit}/100`;
    return `<article class="signal-card execution-pack" data-pack-id="${esc(pack.id)}">
      <div class="signal-top">
        <div>
          <div class="eyebrow">MARKET ${esc(pack.priority_score)}/100 · ${esc(stage.toUpperCase())}</div>
          <div class="signal-title">${esc(pack.contractor_name)}</div>
          <div class="signal-meta">
            <span class="pill">${esc(pack.category_label || pack.category)}</span>
            <span class="pill">${esc(pack.related_opportunity_count || 0)} signals</span>
            <span class="pill">${esc(pack.primary_tender_code || '—')}</span>
          </div>
        </div>
        <div class="signal-score ${m.personalFit >= 70 ? 'hot' : 'watch'}">${esc(m.personalFit == null ? pack.priority_score : m.personalFit)}</div>
      </div>

      <div class="signal-why"><strong>${esc(fitText)}</strong></div>
      <div class="signal-evidence"><strong>Primary buyer:</strong> ${esc(pack.primary_buyer || '—')} · ${esc(pack.primary_tender_title || '')}</div>
      <div class="signal-evidence"><strong>Offer cần kiểm chứng:</strong> ${esc(pack.offer_to_validate || '—')}</div>
      <div class="muted small" style="margin-top:6px">${esc(m.reasons.join(' '))}</div>
      ${relatedSignalsHtml(pack)}
      <div class="signal-evidence" style="margin-top:9px"><strong>Bằng chứng lịch sử:</strong> ${esc(historical.latest_win_title || '—')} · ${esc(historical.observed_wins_same_category || 0)} win cùng nhóm quan sát.</div>
      <div style="margin-top:8px"><strong>Contact đã xác minh:</strong>${contactHtml(pack.verified_contact_paths)}</div>

      <details style="margin-top:10px">
        <summary style="cursor:pointer;font-weight:700">Xem draft + send gates</summary>
        <div style="margin-top:9px">
          <div class="muted small"><strong>Subject:</strong> ${esc(pack.outreach_subject_draft)}</div>
          <pre style="white-space:pre-wrap;font:inherit;margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:10px">${esc(pack.outreach_body_draft)}</pre>
          <div style="margin-top:8px"><strong>Chỉ gửi khi:</strong><ul>${(pack.send_gates || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
          <div class="muted small"><strong>Follow-up:</strong> ${esc(pack.follow_up_rule)}</div>
        </div>
      </details>

      <label style="display:block;margin-top:10px;font-weight:700">Bằng chứng năng lực thật của bạn</label>
      <textarea class="execution-proof" rows="3" placeholder="Dự án đã làm, partner thực hiện thật, thiết bị/nhân sự đang có, rate card…">${esc(proof)}</textarea>
      <label style="display:block;margin-top:8px;font-weight:700">Ghi chú kết quả</label>
      <textarea class="execution-note" rows="2" placeholder="Ai phản hồi? Hỏi gì? Lý do từ chối?">${esc(note)}</textarea>

      <div class="button-row execution-stages" style="margin-top:9px;flex-wrap:wrap">
        ${STAGES.map(([value,label]) => `<button class="btn ${stage === value ? 'secondary' : 'ghost'} execution-stage" data-stage="${value}">${label}</button>`).join('')}
        <button class="btn secondary execution-copy">Sao chép draft</button>
      </div>
      <div class="muted small execution-message" style="margin-top:7px"></div>
      <div class="evidence-links" style="margin-top:8px">
        ${pack.primary_official_tender_url ? `<a href="${esc(safeUrl(pack.primary_official_tender_url))}" target="_blank" rel="noopener noreferrer">TBMT primary</a>` : ''}
        ${historical.latest_evidence_url ? `<a href="${esc(safeUrl(historical.latest_evidence_url))}" target="_blank" rel="noopener noreferrer">KQLCNT lịch sử</a>` : ''}
      </div>
    </article>`;
  }

  function bindExecution(packs){
    const byId = new Map(packs.map(x => [x.id, x]));
    document.querySelectorAll('.execution-pack').forEach(card => {
      const id = card.dataset.packId;
      const pack = byId.get(id);
      if(!pack) return;

      const persist = (patch) => {
        const state = loadExecution();
        state[id] = {...(state[id] || {}), ...patch, updatedAt:new Date().toISOString()};
        saveExecution(state);
      };

      const proof = card.querySelector('.execution-proof');
      const note = card.querySelector('.execution-note');
      proof?.addEventListener('input', () => persist({capabilityProof:proof.value}));
      note?.addEventListener('input', () => persist({note:note.value}));

      card.querySelectorAll('.execution-stage').forEach(btn => {
        btn.addEventListener('click', () => {
          persist({stage:btn.dataset.stage});
          card.querySelectorAll('.execution-stage').forEach(x => x.classList.toggle('secondary', x === btn));
          card.querySelectorAll('.execution-stage').forEach(x => x.classList.toggle('ghost', x !== btn));
          const msg = card.querySelector('.execution-message');
          if(msg) msg.textContent = `Đã lưu trạng thái: ${btn.textContent}.`;
        });
      });

      card.querySelector('.execution-copy')?.addEventListener('click', async () => {
        const profile = loadProfile();
        const match = matchPack(pack, profile);
        const capability = (proof?.value || '').trim();
        const msg = card.querySelector('.execution-message');
        if(!profileComplete(profile)){
          if(msg) msg.textContent = 'Chưa cho phép copy: hãy hoàn thành tab My Edge trước.';
          return;
        }
        if(match.classification === 'not_for_you'){
          if(msg) msg.textContent = 'Chưa cho phép copy: Personal Edge đang xếp campaign này là NOT FOR YOU. Hãy tìm campaign khác hoặc cập nhật profile bằng năng lực thật.';
          return;
        }
        if(!capability){
          if(msg) msg.textContent = 'Chưa cho phép copy: phải nhập bằng chứng năng lực thật trước.';
          return;
        }
        const body = String(pack.outreach_body_draft || '').replace(
          '[CHỈ GỬI SAU KHI BẠN ĐIỀN BẰNG CHỨNG NĂNG LỰC THẬT CỦA MÌNH Ở ĐÂY]',
          capability
        );
        const text = `Subject: ${pack.outreach_subject_draft}\n\n${body}`;
        try{
          await navigator.clipboard.writeText(text);
          if(msg) msg.textContent = 'Đã copy draft có chèn bằng chứng năng lực. Hãy đọc lại trước khi gửi.';
        }catch{
          if(msg) msg.textContent = 'Trình duyệt không cho clipboard tự động. Hãy copy thủ công từ draft.';
        }
      });
    });
  }

  let allPacks = [];

  function renderExecution(packs=allPacks){
    allPacks = packs || [];
    const grid = ensureExecutionSection();
    if(!grid) return;
    const profile = loadProfile();
    const executionState = loadExecution();
    const sorted = [...allPacks].sort((a,b) => combinedScore(b, profile) - combinedScore(a, profile));
    const top = sorted.slice(0,3);
    grid.innerHTML = top.length
      ? top.map(x => packCard(x, executionState, profile)).join('')
      : '<div class="panel muted">Chưa có campaign nào vượt đủ evidence gates. Hệ thống không ép tạo lead giả.</div>';

    const status = document.getElementById('executionQueueStatus');
    if(status){
      const complete = profileComplete(profile);
      status.textContent = complete
        ? `${top.length} campaign ưu tiên theo Personal Edge · profile local-only`
        : `${allPacks.length} campaign ready · hoàn thành My Edge để cá nhân hóa thứ tự`;
    }
    bindExecution(top);
  }

  fetch('data/outreach_intelligence.json', {cache:'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if(!data) return;
      allPacks = data.packs || [];
      ensureEdgeTab();
      renderEdge(allPacks);
      renderExecution(allPacks);
    })
    .catch(() => {});
})();
