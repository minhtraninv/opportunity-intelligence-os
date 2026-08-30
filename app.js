const ACTION_PREF_KEY = 'oi.actionPrefs.v1';

function readActionPrefs(){
  try { return JSON.parse(localStorage.getItem(ACTION_PREF_KEY) || '{}') || {}; }
  catch { return {}; }
}

const savedActionPrefs = readActionPrefs();
const state = {
  data: null,
  capital: Number(savedActionPrefs.capital ?? 10),
  cashDays: Number(savedActionPrefs.cashDays ?? 999),
  geo: savedActionPrefs.geo || 'all',
  selectedOpportunity: null,
  rawFeed: {items: [], updated_at: null},
  intelligence: {
    meta: {status: 'warming_up', history_days: 0, required_history_days: 14},
    category_changes: [], coverage: {}, warnings: []
  },
};

const CATEGORY_LABELS = {
  fdi_industrial: 'FDI & sản xuất công nghiệp', infrastructure: 'Hạ tầng & đầu tư công',
  data_ai: 'AI · Data Center · Bán dẫn', sme: 'SME & hộ kinh doanh',
  energy: 'Điện & năng lượng', logistics: 'Logistics & kho vận',
};
const TREND_LABELS = {
  accelerating:'↑ Tăng tốc', emerging:'NEW · Emerging', single_source_spike:'⚠ Spike một nguồn',
  stable:'→ Chưa bất thường', cooling:'↓ Hạ nhiệt', insufficient_sample:'Thiếu mẫu', warming_up:'Đang học baseline',
};
const EVENT_TYPE_LABELS = {
  procurement:'Đấu thầu / mua sắm', hiring:'Tuyển dụng', capex_expansion:'CAPEX / mở rộng',
  infrastructure_delivery:'Hạ tầng triển khai', capital_flow:'Dòng vốn', policy_regulation:'Chính sách / pháp lý',
  business_formation:'Doanh nghiệp / hộ KD', market_data:'Dữ liệu thị trường', other:'Chưa phân loại',
};
const QUALITY_LABELS = {curated:'Curated', candidate:'Candidate', reference:'Reference', noise:'Noise'};

const esc = (value) => String(value ?? '')
  .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
  .replaceAll('"','&quot;').replaceAll("'",'&#039;');
const safeUrl = (value) => { try { const u = new URL(value); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
const fmtDate = (iso) => { try { return new Intl.DateTimeFormat('vi-VN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(iso)); } catch { return iso || '—'; } };
const money = (m) => m < 1 ? '<1 triệu' : `${m} triệu`;
const daysText = (d) => d <= 14 ? '≤ 2 tuần' : d <= 30 ? '≤ 1 tháng' : d <= 90 ? '≤ 3 tháng' : d <= 180 ? '≤ 6 tháng' : `${d} ngày`;
const clamp = (n,min,max) => Math.max(min,Math.min(max,n));

function saveActionPrefs(){
  localStorage.setItem(ACTION_PREF_KEY, JSON.stringify({capital:state.capital,cashDays:state.cashDays,geo:state.geo,updatedAt:new Date().toISOString()}));
}
function syncActionControls(){
  const capital = document.getElementById('capitalFilter');
  const cash = document.getElementById('cashFilter');
  const geo = document.getElementById('geoFilter');
  if(capital && [...capital.options].some(x=>Number(x.value)===state.capital)) capital.value = String(state.capital);
  if(cash && [...cash.options].some(x=>Number(x.value)===state.cashDays)) cash.value = String(state.cashDays);
  if(geo && [...geo.options].some(x=>x.value===state.geo)) geo.value = state.geo;
}
function latestTimestamp(...values){
  const valid = values.filter(Boolean).map(x=>new Date(x)).filter(x=>!Number.isNaN(x.getTime()));
  return valid.length ? new Date(Math.max(...valid.map(x=>x.getTime()))).toISOString() : null;
}

/* Action Layer scores priority. It never decides what the radar is allowed to see. */
function capitalFit(opp, capital){
  const min = Number(opp.capital_min_m || 0);
  const max = Math.max(min + 1, Number(opp.capital_max_m || min + 1));
  if(capital < min) return clamp(Math.round((capital / Math.max(1,min)) * 45), 5, 45);
  if(capital >= max) return 100;
  return clamp(Math.round(65 + ((capital-min)/(max-min))*35), 0, 100);
}
function timeFit(opp){
  if(state.cashDays >= 999) return 80;
  const d = Number(opp.time_to_cash_days || 999);
  if(d <= state.cashDays) return 100;
  return clamp(Math.round(100 * state.cashDays / Math.max(state.cashDays,d)), 20, 85);
}
function geoFit(opp){
  if(state.geo === 'all') return 90;
  if(opp.geo === 'national' || opp.geo === state.geo) return 100;
  return 35;
}
function personalizedScore(opp){
  const competition = clamp(100 - Number(opp.competition_score || 50), 0, 100);
  return Math.round(
    Number(opp.evidence_score || 0) * 0.35 +
    Number(opp.buyer_clarity_score || 0) * 0.20 +
    capitalFit(opp,state.capital) * 0.15 +
    timeFit(opp) * 0.10 +
    geoFit(opp) * 0.05 +
    competition * 0.15
  );
}
function actionFitNote(opp){
  const notes = [];
  if(state.capital < Number(opp.capital_min_m || 0)) notes.push('vượt ngân sách test hiện tại');
  if(state.cashDays < 999 && Number(opp.time_to_cash_days || 999) > state.cashDays) notes.push('tín hiệu thương mại chậm hơn mục tiêu');
  if(state.geo !== 'all' && opp.geo !== 'national' && opp.geo !== state.geo) notes.push('ngoài vùng triển khai ưu tiên');
  return notes.length ? notes.join(' · ') : 'nằm trong vùng hành động hiện tại';
}
function rankedOpps(){
  return (state.data?.opportunities || [])
    .map(o=>({...o,personalized_score:personalizedScore(o),action_fit_note:actionFitNote(o)}))
    .sort((a,b)=>b.personalized_score-a.personalized_score);
}
function visibleOpps(){ return rankedOpps(); }

function evidenceLinks(ids){
  const sources = state.data?.sources || [];
  return (ids || []).map(id=>sources.find(s=>s.id===id)).filter(Boolean)
    .map(s=>`<a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.publisher)}</a>`).join('');
}
function signalCard(s){
  const cls = s.score >= 80 ? 'hot' : s.score >= 65 ? 'watch' : 'weak';
  return `<article class="signal-card"><div class="signal-top"><div><div class="signal-title">${esc(s.title)}</div><div class="signal-meta"><span class="pill up">${esc(s.momentum)}</span><span class="pill geo">${esc(s.region)}</span></div></div><div class="signal-score ${cls}">${esc(s.score)}</div></div><div class="signal-why">${esc(s.why_now)}</div><div class="signal-evidence">${esc(s.evidence_summary)}</div><div class="evidence-links">${evidenceLinks(s.source_ids)}</div></article>`;
}
function changeCard(change){
  const active = state.intelligence.meta.status === 'active';
  const trend = change.trend;
  const cls = ['accelerating','emerging'].includes(trend) ? 'hot' : trend === 'cooling' ? 'weak' : 'watch';
  const delta = change.delta_pct == null ? 'chưa tính' : `${change.delta_pct>=0?'+':''}${change.delta_pct}%`;
  return `<article class="signal-card"><div class="signal-top"><div><div class="signal-title">${esc(CATEGORY_LABELS[change.category]||change.category)}</div><div class="signal-meta"><span class="pill ${['accelerating','emerging'].includes(trend)?'up':''}">${esc(TREND_LABELS[trend]||trend)}</span><span class="pill">Confidence ${esc(change.confidence)}/100</span></div></div><div><div class="signal-score ${cls}">${esc(change.recent_7d)}</div><div class="muted small" style="text-align:center;margin-top:4px">7 ngày</div></div></div><div class="signal-why">${esc(change.explanation)}</div><div class="signal-evidence">Baseline 21 ngày: ${esc(change.baseline_21d)} · Quy đổi/7 ngày: ${esc(change.baseline_expected_7d)} · Chênh lệch: ${esc(active?delta:'khóa khi chưa đủ lịch sử')} · Nguồn 7 ngày: ${esc(change.source_diversity_7d)}</div></article>`;
}
function renderChangeDetector(){
  const intel = state.intelligence || {};
  const meta = intel.meta || {};
  const container = document.getElementById('changeDetector');
  const note = document.getElementById('changeDetectorNote');
  if(!container || !note) return;
  if(meta.status === 'warming_up') note.textContent = `Đang học baseline ${meta.history_days||0}/${meta.required_history_days||14} ngày · chưa gọi biến động là trend.`;
  else if(meta.status === 'active') note.textContent = `Baseline hoạt động · recent ${meta.recent_window_days} ngày so với ${meta.baseline_window_days} ngày trước.`;
  else note.textContent = 'Change Detector chưa có dữ liệu.';
  const rows = (intel.category_changes || []).slice(0,6);
  container.innerHTML = rows.length ? rows.map(changeCard).join('') : '<div class="panel muted">Chưa có lịch sử đủ để dựng Change Detector.</div>';
}
function oppCard(o){
  const score = o.personalized_score ?? personalizedScore(o);
  const cls = score >= 80 ? 'good' : score >= 65 ? 'mid' : 'low';
  return `<article class="opp-card">
    <div class="opp-scorebox"><div class="opp-score ${cls}">${score}</div><div class="opp-label">ACTION FIT</div></div>
    <div class="opp-main"><h3>${esc(o.title)}</h3><p>${esc(o.thesis)}</p>
      <div class="opp-tags"><span class="pill">Test vốn ${esc(money(o.capital_min_m))}–${esc(money(o.capital_max_m))}</span><span class="pill">Signal/Cash ${esc(daysText(o.time_to_cash_days))}</span><span class="pill">Buyer ${esc(o.buyer)}</span><span class="pill geo">${esc(o.region)}</span></div>
      <div class="muted small"><strong>Fit hiện tại:</strong> ${esc(o.action_fit_note || actionFitNote(o))}</div>
      <div class="risk"><strong>Điểm yếu:</strong> ${esc(o.primary_risk)}</div>
    </div>
    <div class="opp-actions"><button class="btn primary investigate" data-id="${esc(o.id)}">Điều tra</button><div class="capital-note">Evidence ${esc(o.evidence_score)}/100 · Buyer clarity ${esc(o.buyer_clarity_score)}/100</div></div>
  </article>`;
}
function rawFeedRow(x){
  const quality = x.signal_quality || (x.status === 'verified-seed' ? 'curated' : 'reference');
  const qClass = ['curated','candidate'].includes(quality) ? 'official' : 'hypothesis';
  const eventType = EVENT_TYPE_LABELS[x.event_type] || x.event_type || 'Chưa phân loại';
  const geo = (x.geography || []).join(' · ') || 'Chưa gắn địa lý';
  return `<article class="signal-row"><div class="signal-date">${esc(x.publisher)}<br><span class="tag ${qClass}">${esc(QUALITY_LABELS[quality]||quality)}</span></div><div><h3>${esc(x.title)}</h3><p>${esc((x.categories||[]).map(c=>CATEGORY_LABELS[c]||c).join(' · '))}</p><div class="muted small" style="margin-top:6px">${esc(eventType)} · ${esc(geo)}</div><div class="muted small" style="margin-top:4px">${esc(x.quality_reason||'')}</div><div class="evidence-links" style="margin-top:8px"><a href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener noreferrer">Mở nguồn gốc</a></div></div><div class="signal-side"><span class="muted small">First seen<br>${esc(fmtDate(x.first_seen_at||x.collected_at))}</span></div></article>`;
}

function setText(id,value){ const el=document.getElementById(id); if(el) el.textContent=value; }
function render(){
  const d = state.data; if(!d) return;
  const intel = state.intelligence || {};
  const coverage = intel.coverage || {};
  const meta = intel.meta || {};
  const newest = latestTimestamp(d.meta?.updated_at,state.rawFeed.updated_at,meta.generated_at);
  setText('updatedAt',`Cập nhật ${fmtDate(newest)}`);
  setText('dataStatus',meta.status==='active'?'INTELLIGENCE ACTIVE':'LEARNING BASELINE');
  setText('officialCount',(d.sources||[]).filter(s=>s.authority==='official').length);
  setText('signalCount',(d.signals||[]).length);
  setText('oppCount',(d.opportunities||[]).length);
  setText('buyerCount',(d.buyers||[]).length);
  setText('rawFeedCount',(state.rawFeed.items||[]).length);
  setText('historicalEventCount',coverage.historical_events ?? 0);
  setText('historyDays',`${meta.history_days ?? 0}/${meta.required_history_days ?? 14} ngày`);
  setText('thesisText',d.meta?.current_thesis || '—');
  renderChangeDetector();

  const topSignals = document.getElementById('topSignals');
  if(topSignals) topSignals.innerHTML = (d.signals||[]).slice().sort((a,b)=>b.score-a.score).slice(0,6).map(signalCard).join('');
  const allSignals = document.getElementById('allSignals');
  if(allSignals) allSignals.innerHTML = (d.signals||[]).slice().sort((a,b)=>new Date(b.date)-new Date(a.date)).map(s=>`<article class="signal-row"><div class="signal-date">${esc(new Intl.DateTimeFormat('vi-VN').format(new Date(s.date)))}<br><span class="tag official">Official evidence</span></div><div><h3>${esc(s.title)}</h3><p>${esc(s.why_now)}</p><div class="evidence-links" style="margin-top:8px">${evidenceLinks(s.source_ids)}</div></div><div class="signal-side"><strong>${esc(s.score)}/100</strong><br><span class="muted small">${esc(s.momentum)}</span><br><span class="tag hypothesis">${esc(s.stage)}</span></div></article>`).join('');

  const opps = rankedOpps();
  const topOpps = document.getElementById('topOpportunities');
  const allOpps = document.getElementById('allOpportunities');
  if(topOpps) topOpps.innerHTML = opps.slice(0,5).map(oppCard).join('') || '<div class="panel muted">Chưa có Small Bet hypotheses.</div>';
  if(allOpps) allOpps.innerHTML = opps.map(oppCard).join('') || '<div class="panel muted">Chưa có Small Bet hypotheses.</div>';

  const raw = (state.rawFeed.items||[]).slice().sort((a,b)=>{
    const q = x => x.signal_quality==='curated'?3:x.signal_quality==='candidate'?2:1;
    return q(b)-q(a) || new Date(b.first_seen_at||b.collected_at||0)-new Date(a.first_seen_at||a.collected_at||0);
  }).slice(0,60);
  const rawFeed = document.getElementById('rawFeed');
  if(rawFeed) rawFeed.innerHTML = raw.length ? raw.map(rawFeedRow).join('') : '<div class="panel muted">Chưa có headline mới.</div>';

  const buyerGrid = document.getElementById('buyerGrid');
  if(buyerGrid) buyerGrid.innerHTML = (d.buyers||[]).map(b=>`<article class="buyer-card"><div class="eyebrow">${esc(b.sector)}</div><h3>${esc(b.role)}</h3><div class="trigger"><strong>Trigger:</strong> ${esc(b.trigger)}</div><ul>${(b.likely_buys||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><div class="muted small"><strong>Cách tiếp cận:</strong> ${esc(b.access_path)}</div></article>`).join('');
  bindInvestigate();
}

function bindInvestigate(){
  document.querySelectorAll('.investigate').forEach(btn=>btn.addEventListener('click',()=>{state.selectedOpportunity=btn.dataset.id;openValidation(btn.dataset.id);}));
}
function openValidation(id){
  const o = state.data?.opportunities?.find(x=>x.id===id); if(!o) return;
  setText('validateTitle',o.title);
  setText('validateIntro','Mục tiêu: mua thông tin về giả thuyết bằng một test nhỏ trước khi tăng cược.');
  const body = document.getElementById('validationBody');
  if(body) body.innerHTML = `<div class="opp-tags"><span class="pill">Ngân sách test: ${esc(o.test_budget_m)} triệu</span><span class="pill">${esc(o.region)}</span><span class="pill">${esc(daysText(o.time_to_cash_days))}</span></div><h3>Kế hoạch test</h3><ol class="checklist">${(o.validation_steps||[]).map((x,i)=>`<li><span class="step-num">${i+1}</span><span>${esc(x)}</span></li>`).join('')}</ol><div class="kill-box"><strong>Kill criteria</strong><div>${esc(o.kill_criteria)}</div></div><h3 style="margin-top:16px">Bằng chứng gốc</h3><div class="evidence-links">${evidenceLinks(o.source_ids)}</div>`;
  switchTab('validate');
  const notes = document.getElementById('fieldNotes'); if(notes) notes.value = localStorage.getItem(`oi-notes-${id}`)||'';
}
function switchTab(id){
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));
  document.querySelectorAll('.tab-view').forEach(x=>x.classList.toggle('active',x.id===id));
  window.scrollTo({top:0,behavior:'smooth'});
}

document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.tab)));
syncActionControls();
document.getElementById('capitalFilter')?.addEventListener('change',e=>{state.capital=Number(e.target.value);saveActionPrefs();render();});
document.getElementById('cashFilter')?.addEventListener('change',e=>{state.cashDays=Number(e.target.value);saveActionPrefs();render();});
document.getElementById('geoFilter')?.addEventListener('change',e=>{state.geo=e.target.value;saveActionPrefs();render();});
document.getElementById('saveNotes')?.addEventListener('click',()=>{
  if(!state.selectedOpportunity){setText('noteStatus','Chưa chọn Small Bet.');return;}
  localStorage.setItem(`oi-notes-${state.selectedOpportunity}`,document.getElementById('fieldNotes')?.value||''); setText('noteStatus','Đã lưu cục bộ.');
});
document.getElementById('clearNotes')?.addEventListener('click',()=>{
  if(state.selectedOpportunity) localStorage.removeItem(`oi-notes-${state.selectedOpportunity}`);
  const notes=document.getElementById('fieldNotes'); if(notes) notes.value=''; setText('noteStatus','Đã xóa.');
});

Promise.all([
  fetch('data/radar.json',{cache:'no-store'}).then(r=>{if(!r.ok) throw new Error(`radar HTTP ${r.status}`);return r.json();}),
  fetch('data/raw_feed.json',{cache:'no-store'}).then(r=>r.ok?r.json():({items:[]})).catch(()=>({items:[]})),
  fetch('data/intelligence.json',{cache:'no-store'}).then(r=>r.ok?r.json():state.intelligence).catch(()=>state.intelligence)
]).then(([data,raw,intelligence])=>{
  state.data=data; state.rawFeed=raw||{items:[]}; state.intelligence=intelligence||state.intelligence; render();
}).catch(err=>{
  setText('updatedAt','Không tải được dữ liệu lõi'); setText('dataStatus','ERROR'); setText('thesisText',`Lỗi dữ liệu: ${err.message}`);
});
