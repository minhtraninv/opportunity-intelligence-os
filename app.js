const state = {
  data: null,
  capital: 50,
  cashDays: 999,
  geo: 'all',
  selectedOpportunity: null,
  rawFeed: {items: [], updated_at: null},
  intelligence: {
    meta: {status: 'warming_up', history_days: 0, required_history_days: 14},
    category_changes: [],
    coverage: {},
    warnings: []
  },
};

const CATEGORY_LABELS = {
  fdi_industrial: 'FDI & sản xuất công nghiệp',
  infrastructure: 'Hạ tầng & đầu tư công',
  data_ai: 'AI · Data Center · Bán dẫn',
  sme: 'SME & hộ kinh doanh',
  energy: 'Điện & năng lượng',
  logistics: 'Logistics & kho vận',
};

const TREND_LABELS = {
  accelerating: '↑ Tăng tốc',
  emerging: 'NEW · Emerging',
  single_source_spike: '⚠ Spike một nguồn',
  stable: '→ Chưa bất thường',
  cooling: '↓ Hạ nhiệt',
  insufficient_sample: 'Thiếu mẫu',
  warming_up: 'Đang học baseline',
};

const EVENT_TYPE_LABELS = {
  procurement: 'Đấu thầu / mua sắm',
  hiring: 'Tuyển dụng',
  capex_expansion: 'CAPEX / mở rộng',
  infrastructure_delivery: 'Hạ tầng triển khai',
  capital_flow: 'Dòng vốn',
  policy_regulation: 'Chính sách / pháp lý',
  business_formation: 'Doanh nghiệp / hộ KD',
  market_data: 'Dữ liệu thị trường',
  other: 'Chưa phân loại',
};

const QUALITY_LABELS = {
  curated: 'Curated',
  candidate: 'Candidate',
  reference: 'Reference',
  noise: 'Noise',
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
  } catch {
    return '#';
  }
};

const fmtDate = (iso) => {
  try { return new Intl.DateTimeFormat('vi-VN', {dateStyle:'medium', timeStyle:'short'}).format(new Date(iso)); }
  catch { return iso || '—'; }
};
const money = (m) => m < 1 ? '<1 triệu' : `${m} triệu`;
const daysText = (d) => d <= 14 ? '≤ 2 tuần' : d <= 30 ? '≤ 1 tháng' : d <= 90 ? '≤ 3 tháng' : `${d} ngày`;
const clamp = (n,min,max) => Math.max(min,Math.min(max,n));

function latestTimestamp(...values){
  const valid = values.filter(Boolean).map(x => new Date(x)).filter(x => !Number.isNaN(x.getTime()));
  if(!valid.length) return null;
  return new Date(Math.max(...valid.map(x=>x.getTime()))).toISOString();
}

function capitalFit(opp, capital){
  if (capital < opp.capital_min_m) return 0;
  if (capital >= opp.capital_max_m) return 100;
  const range = Math.max(1, opp.capital_max_m - opp.capital_min_m);
  return clamp(65 + ((capital - opp.capital_min_m)/range)*35, 0, 100);
}

function personalizedScore(opp){
  const cfit = capitalFit(opp, state.capital);
  const time = clamp(100 - ((opp.time_to_cash_days - 7) * 0.75), 20, 100);
  const competition = clamp(100 - opp.competition_score, 0, 100);
  return Math.round(
    opp.evidence_score * 0.30 +
    cfit * 0.25 +
    time * 0.20 +
    opp.buyer_clarity_score * 0.15 +
    competition * 0.10
  );
}

function visibleOpps(){
  return state.data.opportunities
    .filter(o => state.capital >= o.capital_min_m)
    .filter(o => o.time_to_cash_days <= state.cashDays)
    .filter(o => state.geo === 'all' || o.geo === state.geo || o.geo === 'national')
    .map(o => ({...o, personalized_score: personalizedScore(o)}))
    .sort((a,b)=>b.personalized_score-a.personalized_score);
}

function evidenceLinks(ids){
  const sources = state.data.sources;
  return ids.map(id => sources.find(s=>s.id===id)).filter(Boolean)
    .map(s => `<a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.publisher)}</a>`).join('');
}

function signalCard(s){
  const scoreClass = s.score >= 80 ? 'hot' : s.score >= 65 ? 'watch' : 'weak';
  return `<article class="signal-card">
    <div class="signal-top">
      <div>
        <div class="signal-title">${esc(s.title)}</div>
        <div class="signal-meta"><span class="pill up">${esc(s.momentum)}</span><span class="pill geo">${esc(s.region)}</span></div>
      </div>
      <div class="signal-score ${scoreClass}">${esc(s.score)}</div>
    </div>
    <div class="signal-why">${esc(s.why_now)}</div>
    <div class="signal-evidence">${esc(s.evidence_summary)}</div>
    <div class="evidence-links">${evidenceLinks(s.source_ids)}</div>
  </article>`;
}

function changeCard(change){
  const active = state.intelligence.meta.status === 'active';
  const trend = change.trend;
  const scoreClass = trend === 'accelerating' || trend === 'emerging' ? 'hot' : trend === 'cooling' ? 'weak' : 'watch';
  const delta = change.delta_pct === null || change.delta_pct === undefined
    ? 'chưa tính'
    : `${change.delta_pct >= 0 ? '+' : ''}${change.delta_pct}%`;

  return `<article class="signal-card">
    <div class="signal-top">
      <div>
        <div class="signal-title">${esc(CATEGORY_LABELS[change.category] || change.category)}</div>
        <div class="signal-meta">
          <span class="pill ${trend === 'accelerating' || trend === 'emerging' ? 'up' : ''}">${esc(TREND_LABELS[trend] || trend)}</span>
          <span class="pill">Confidence ${esc(change.confidence)}/100</span>
        </div>
      </div>
      <div>
        <div class="signal-score ${scoreClass}">${esc(change.recent_7d)}</div>
        <div class="muted small" style="text-align:center;margin-top:4px">7 ngày</div>
      </div>
    </div>
    <div class="signal-why">${esc(change.explanation)}</div>
    <div class="signal-evidence">Baseline 21 ngày: ${esc(change.baseline_21d)} · Quy đổi/7 ngày: ${esc(change.baseline_expected_7d)} · Chênh lệch: ${esc(active ? delta : 'khóa khi chưa đủ lịch sử')} · Nguồn 7 ngày: ${esc(change.source_diversity_7d)}</div>
  </article>`;
}

function renderChangeDetector(){
  const intel = state.intelligence;
  const meta = intel.meta || {};
  const container = document.getElementById('changeDetector');
  const note = document.getElementById('changeDetectorNote');

  if(!container || !note) return;

  if(meta.status === 'warming_up'){
    note.textContent = `Đang học baseline ${meta.history_days || 0}/${meta.required_history_days || 14} ngày · chỉ Candidate events được tính.`;
  } else if(meta.status === 'active'){
    note.textContent = `Baseline hoạt động · recent ${meta.recent_window_days} ngày so với ${meta.baseline_window_days} ngày trước.`;
  } else {
    note.textContent = 'Change Detector chưa có dữ liệu.';
  }

  const rows = (intel.category_changes || []).slice(0,6);
  if(rows.length){
    container.innerHTML = rows.map(changeCard).join('');
  } else {
    container.innerHTML = '<div class="panel muted">Chưa có lịch sử đủ để dựng Change Detector. Pipeline sẽ tự tích lũy sau mỗi lần chạy.</div>';
  }
}

function oppCard(o){
  const score = o.personalized_score ?? personalizedScore(o);
  const scoreClass = score >= 80 ? 'good' : score >= 65 ? 'mid' : 'low';
  return `<article class="opp-card">
    <div class="opp-scorebox"><div class="opp-score ${scoreClass}">${score}</div><div class="opp-label">FIT SCORE</div></div>
    <div class="opp-main">
      <h3>${esc(o.title)}</h3>
      <p>${esc(o.thesis)}</p>
      <div class="opp-tags">
        <span class="pill">Vốn ${esc(money(o.capital_min_m))}–${esc(money(o.capital_max_m))}</span>
        <span class="pill">Cash ${esc(daysText(o.time_to_cash_days))}</span>
        <span class="pill">Buyer ${esc(o.buyer)}</span>
        <span class="pill geo">${esc(o.region)}</span>
      </div>
      <div class="risk"><strong>Điểm yếu:</strong> ${esc(o.primary_risk)}</div>
    </div>
    <div class="opp-actions">
      <button class="btn primary investigate" data-id="${esc(o.id)}">Điều tra</button>
      <div class="capital-note">Evidence ${esc(o.evidence_score)}/100 · Buyer clarity ${esc(o.buyer_clarity_score)}/100</div>
    </div>
  </article>`;
}

function rawFeedRow(x){
  const quality = x.signal_quality || (x.status === 'verified-seed' ? 'curated' : 'reference');
  const qualityClass = quality === 'curated' || quality === 'candidate' ? 'official' : 'hypothesis';
  const eventType = EVENT_TYPE_LABELS[x.event_type] || x.event_type || 'Chưa phân loại';
  const geo = (x.geography || []).join(' · ') || 'Chưa gắn địa lý';
  return `<article class="signal-row">
    <div class="signal-date">${esc(x.publisher)}<br><span class="tag ${qualityClass}">${esc(QUALITY_LABELS[quality] || quality)}</span></div>
    <div>
      <h3>${esc(x.title)}</h3>
      <p>${esc((x.categories||[]).map(c=>CATEGORY_LABELS[c] || c).join(' · '))}</p>
      <div class="muted small" style="margin-top:6px">${esc(eventType)} · ${esc(geo)}</div>
      <div class="muted small" style="margin-top:4px">${esc(x.quality_reason || '')}</div>
      <div class="evidence-links" style="margin-top:8px"><a href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener noreferrer">Mở nguồn gốc</a></div>
    </div>
    <div class="signal-side"><span class="muted small">First seen<br>${esc(fmtDate(x.first_seen_at || x.collected_at))}</span></div>
  </article>`;
}

function render(){
  const d = state.data;
  const intel = state.intelligence || {};
  const coverage = intel.coverage || {};
  const meta = intel.meta || {};
  const newest = latestTimestamp(d.meta.updated_at, state.rawFeed.updated_at, meta.generated_at);

  document.getElementById('updatedAt').textContent = `Cập nhật ${fmtDate(newest)}`;
  document.getElementById('dataStatus').textContent = meta.status === 'active' ? 'V1.2 · INTELLIGENCE ACTIVE' : 'V1.2 · LEARNING BASELINE';
  document.getElementById('officialCount').textContent = d.sources.filter(s=>s.authority==='official').length;
  document.getElementById('signalCount').textContent = d.signals.length;
  document.getElementById('oppCount').textContent = d.opportunities.length;
  document.getElementById('buyerCount').textContent = d.buyers.length;
  document.getElementById('rawFeedCount').textContent = state.rawFeed.items.length;
  document.getElementById('historicalEventCount').textContent = coverage.historical_events ?? 0;
  document.getElementById('historyDays').textContent = `${meta.history_days ?? 0}/${meta.required_history_days ?? 14} ngày`;
  const candidateEl = document.getElementById('candidateEventCount');
  const referenceEl = document.getElementById('referenceEventCount');
  if(candidateEl) candidateEl.textContent = coverage.candidate_events ?? 0;
  if(referenceEl) referenceEl.textContent = coverage.reference_events ?? 0;
  document.getElementById('thesisText').textContent = d.meta.current_thesis;

  renderChangeDetector();

  document.getElementById('topSignals').innerHTML = d.signals.slice().sort((a,b)=>b.score-a.score).slice(0,6).map(signalCard).join('');
  document.getElementById('allSignals').innerHTML = d.signals.slice().sort((a,b)=>new Date(b.date)-new Date(a.date)).map(s=>`
    <article class="signal-row">
      <div class="signal-date">${esc(new Intl.DateTimeFormat('vi-VN').format(new Date(s.date)))}<br><span class="tag official">Official evidence</span></div>
      <div><h3>${esc(s.title)}</h3><p>${esc(s.why_now)}</p><div class="evidence-links" style="margin-top:8px">${evidenceLinks(s.source_ids)}</div></div>
      <div class="signal-side"><strong>${esc(s.score)}/100</strong><br><span class="muted small">${esc(s.momentum)}</span><br><span class="tag hypothesis">${esc(s.stage)}</span></div>
    </article>`).join('');

  const opps = visibleOpps();
  document.getElementById('topOpportunities').innerHTML = opps.slice(0,5).map(oppCard).join('') || '<div class="panel muted">Không có cơ hội nào qua bộ lọc hiện tại.</div>';
  document.getElementById('allOpportunities').innerHTML = opps.map(oppCard).join('') || '<div class="panel muted">Không có cơ hội nào qua bộ lọc hiện tại.</div>';

  const raw = state.rawFeed.items.slice().sort((a,b)=>{
    const qa = a.signal_quality === 'candidate' ? 2 : a.signal_quality === 'curated' ? 3 : 1;
    const qb = b.signal_quality === 'candidate' ? 2 : b.signal_quality === 'curated' ? 3 : 1;
    if(qb !== qa) return qb - qa;
    return new Date(b.first_seen_at || b.collected_at || 0) - new Date(a.first_seen_at || a.collected_at || 0);
  }).slice(0,60);
  document.getElementById('rawFeed').innerHTML = raw.length ? raw.map(rawFeedRow).join('') : '<div class="panel muted">Chưa có headline mới. Curated signals phía trên vẫn hoạt động bình thường.</div>';

  document.getElementById('buyerGrid').innerHTML = d.buyers.map(b=>`<article class="buyer-card">
    <div class="eyebrow">${esc(b.sector)}</div><h3>${esc(b.role)}</h3>
    <div class="trigger"><strong>Trigger:</strong> ${esc(b.trigger)}</div>
    <ul>${b.likely_buys.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
    <div class="muted small"><strong>Cách tiếp cận:</strong> ${esc(b.access_path)}</div>
  </article>`).join('');

  bindInvestigate();
}

function bindInvestigate(){
  document.querySelectorAll('.investigate').forEach(btn=>btn.addEventListener('click',()=>{
    state.selectedOpportunity = btn.dataset.id;
    openValidation(btn.dataset.id);
  }));
}

function openValidation(id){
  const o = state.data.opportunities.find(x=>x.id===id);
  if(!o) return;
  document.getElementById('validateTitle').textContent = o.title;
  document.getElementById('validateIntro').textContent = 'Mục tiêu: kiểm tra xem buyer thật có chịu trả tiền hay không trước khi bỏ vốn lớn.';
  document.getElementById('validationBody').innerHTML = `
    <div class="opp-tags"><span class="pill">Ngân sách test: ${esc(o.test_budget_m)} triệu</span><span class="pill">${esc(o.region)}</span><span class="pill">${esc(daysText(o.time_to_cash_days))}</span></div>
    <h3>Kế hoạch test</h3>
    <ol class="checklist">${o.validation_steps.map((x,i)=>`<li><span class="step-num">${i+1}</span><span>${esc(x)}</span></li>`).join('')}</ol>
    <div class="kill-box"><strong>Kill criteria</strong><div>${esc(o.kill_criteria)}</div></div>
    <h3 style="margin-top:16px">Bằng chứng gốc</h3><div class="evidence-links">${evidenceLinks(o.source_ids)}</div>`;
  switchTab('validate');
  const saved = localStorage.getItem(`oi-notes-${id}`) || '';
  document.getElementById('fieldNotes').value = saved;
}

function switchTab(id){
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));
  document.querySelectorAll('.tab-view').forEach(x=>x.classList.toggle('active',x.id===id));
  window.scrollTo({top:0,behavior:'smooth'});
}

document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.tab)));
document.getElementById('capitalFilter').addEventListener('change',e=>{state.capital=Number(e.target.value);render();});
document.getElementById('cashFilter').addEventListener('change',e=>{state.cashDays=Number(e.target.value);render();});
document.getElementById('geoFilter').addEventListener('change',e=>{state.geo=e.target.value;render();});
document.getElementById('saveNotes').addEventListener('click',()=>{
  if(!state.selectedOpportunity){document.getElementById('noteStatus').textContent='Chưa chọn cơ hội.';return;}
  localStorage.setItem(`oi-notes-${state.selectedOpportunity}`,document.getElementById('fieldNotes').value);
  document.getElementById('noteStatus').textContent='Đã lưu cục bộ.';
});
document.getElementById('clearNotes').addEventListener('click',()=>{
  if(state.selectedOpportunity) localStorage.removeItem(`oi-notes-${state.selectedOpportunity}`);
  document.getElementById('fieldNotes').value='';
  document.getElementById('noteStatus').textContent='Đã xóa.';
});

Promise.all([
  fetch('data/radar.json', {cache:'no-store'}).then(r=>{if(!r.ok) throw new Error(`radar HTTP ${r.status}`); return r.json();}),
  fetch('data/raw_feed.json', {cache:'no-store'}).then(r=>r.ok?r.json():({items:[]})).catch(()=>({items:[]})),
  fetch('data/intelligence.json', {cache:'no-store'}).then(r=>r.ok?r.json():state.intelligence).catch(()=>state.intelligence)
])
  .then(([data, raw, intelligence])=>{
    state.data=data;
    state.rawFeed=raw || {items:[]};
    state.intelligence=intelligence || state.intelligence;
    render();
  })
  .catch(err=>{
    document.getElementById('updatedAt').textContent='Không tải được dữ liệu lõi';
    document.getElementById('dataStatus').textContent='ERROR';
    document.getElementById('thesisText').textContent=`Lỗi dữ liệu: ${err.message}`;
  });
