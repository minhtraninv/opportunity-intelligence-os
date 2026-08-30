const state = {
  data: null,
  capital: 50,
  cashDays: 999,
  geo: 'all',
  selectedOpportunity: null,
  rawFeed: {items: [], updated_at: null},
};

const fmtDate = (iso) => {
  try { return new Intl.DateTimeFormat('vi-VN', {dateStyle:'medium', timeStyle:'short'}).format(new Date(iso)); }
  catch { return iso; }
};
const money = (m) => m < 1 ? '<1 triệu' : `${m} triệu`;
const daysText = (d) => d <= 14 ? '≤ 2 tuần' : d <= 30 ? '≤ 1 tháng' : d <= 90 ? '≤ 3 tháng' : `${d} ngày`;
const clamp = (n,min,max) => Math.max(min,Math.min(max,n));

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
    .map(s => `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.publisher}</a>`).join('');
}

function signalCard(s){
  const scoreClass = s.score >= 80 ? 'hot' : s.score >= 65 ? 'watch' : 'weak';
  return `<article class="signal-card">
    <div class="signal-top">
      <div>
        <div class="signal-title">${s.title}</div>
        <div class="signal-meta"><span class="pill up">${s.momentum}</span><span class="pill geo">${s.region}</span></div>
      </div>
      <div class="signal-score ${scoreClass}">${s.score}</div>
    </div>
    <div class="signal-why">${s.why_now}</div>
    <div class="signal-evidence">${s.evidence_summary}</div>
    <div class="evidence-links">${evidenceLinks(s.source_ids)}</div>
  </article>`;
}

function oppCard(o){
  const score = o.personalized_score ?? personalizedScore(o);
  const scoreClass = score >= 80 ? 'good' : score >= 65 ? 'mid' : 'low';
  return `<article class="opp-card">
    <div class="opp-scorebox"><div class="opp-score ${scoreClass}">${score}</div><div class="opp-label">FIT SCORE</div></div>
    <div class="opp-main">
      <h3>${o.title}</h3>
      <p>${o.thesis}</p>
      <div class="opp-tags">
        <span class="pill">Vốn ${money(o.capital_min_m)}–${money(o.capital_max_m)}</span>
        <span class="pill">Cash ${daysText(o.time_to_cash_days)}</span>
        <span class="pill">Buyer ${o.buyer}</span>
        <span class="pill geo">${o.region}</span>
      </div>
      <div class="risk"><strong>Điểm yếu:</strong> ${o.primary_risk}</div>
    </div>
    <div class="opp-actions">
      <button class="btn primary investigate" data-id="${o.id}">Điều tra</button>
      <div class="capital-note">Evidence ${o.evidence_score}/100 · Buyer clarity ${o.buyer_clarity_score}/100</div>
    </div>
  </article>`;
}

function render(){
  const d = state.data;
  document.getElementById('updatedAt').textContent = `Cập nhật ${fmtDate(d.meta.updated_at)}`;
  document.getElementById('dataStatus').textContent = d.meta.mode.toUpperCase();
  document.getElementById('officialCount').textContent = d.sources.filter(s=>s.authority==='official').length;
  document.getElementById('signalCount').textContent = d.signals.length;
  document.getElementById('oppCount').textContent = d.opportunities.length;
  document.getElementById('buyerCount').textContent = d.buyers.length;
  document.getElementById('rawFeedCount').textContent = state.rawFeed.items.length;
  document.getElementById('thesisText').textContent = d.meta.current_thesis;

  document.getElementById('topSignals').innerHTML = d.signals.slice().sort((a,b)=>b.score-a.score).slice(0,6).map(signalCard).join('');
  document.getElementById('allSignals').innerHTML = d.signals.slice().sort((a,b)=>new Date(b.date)-new Date(a.date)).map(s=>`
    <article class="signal-row">
      <div class="signal-date">${new Intl.DateTimeFormat('vi-VN').format(new Date(s.date))}<br><span class="tag official">Official evidence</span></div>
      <div><h3>${s.title}</h3><p>${s.why_now}</p><div class="evidence-links" style="margin-top:8px">${evidenceLinks(s.source_ids)}</div></div>
      <div class="signal-side"><strong>${s.score}/100</strong><br><span class="muted small">${s.momentum}</span><br><span class="tag hypothesis">${s.stage}</span></div>
    </article>`).join('');

  const opps = visibleOpps();
  document.getElementById('topOpportunities').innerHTML = opps.slice(0,5).map(oppCard).join('') || '<div class="panel muted">Không có cơ hội nào qua bộ lọc hiện tại.</div>';
  document.getElementById('allOpportunities').innerHTML = opps.map(oppCard).join('') || '<div class="panel muted">Không có cơ hội nào qua bộ lọc hiện tại.</div>';


  const raw = state.rawFeed.items.slice(0,40);
  document.getElementById('rawFeed').innerHTML = raw.length ? raw.map(x=>`
    <article class="signal-row">
      <div class="signal-date">${x.publisher}<br><span class="tag ${x.status === 'verified-seed' ? 'official' : 'hypothesis'}">${x.status}</span></div>
      <div><h3>${x.title}</h3><p>${(x.categories||[]).join(' · ')}</p><div class="evidence-links" style="margin-top:8px"><a href="${x.url}" target="_blank" rel="noopener noreferrer">Mở nguồn gốc</a></div></div>
      <div class="signal-side"><span class="muted small">${fmtDate(x.collected_at)}</span></div>
    </article>`).join('') : '<div class="panel muted">Chưa có headline mới. Curated signals phía trên vẫn hoạt động bình thường.</div>';

  document.getElementById('buyerGrid').innerHTML = d.buyers.map(b=>`<article class="buyer-card">
    <div class="eyebrow">${b.sector}</div><h3>${b.role}</h3>
    <div class="trigger"><strong>Trigger:</strong> ${b.trigger}</div>
    <ul>${b.likely_buys.map(x=>`<li>${x}</li>`).join('')}</ul>
    <div class="muted small"><strong>Cách tiếp cận:</strong> ${b.access_path}</div>
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
  document.getElementById('validateIntro').textContent = `Mục tiêu: kiểm tra xem buyer thật có chịu trả tiền hay không trước khi bỏ vốn lớn.`;
  document.getElementById('validationBody').innerHTML = `
    <div class="opp-tags"><span class="pill">Ngân sách test: ${o.test_budget_m} triệu</span><span class="pill">${o.region}</span><span class="pill">${daysText(o.time_to_cash_days)}</span></div>
    <h3>Kế hoạch test</h3>
    <ol class="checklist">${o.validation_steps.map((x,i)=>`<li><span class="step-num">${i+1}</span><span>${x}</span></li>`).join('')}</ol>
    <div class="kill-box"><strong>Kill criteria</strong><div>${o.kill_criteria}</div></div>
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
  fetch('data/raw_feed.json', {cache:'no-store'}).then(r=>r.ok?r.json():({items:[]})).catch(()=>({items:[]}))
])
  .then(([data, raw])=>{
    state.data=data;
    state.rawFeed=raw || {items:[]};
    if(raw && raw.updated_at && new Date(raw.updated_at) > new Date(data.meta.updated_at)){
      state.data.meta.updated_at = raw.updated_at;
    }
    render();
  })
  .catch(err=>{
    document.getElementById('updatedAt').textContent='Không tải được data/radar.json';
    document.getElementById('dataStatus').textContent='ERROR';
    document.getElementById('thesisText').textContent=`Lỗi dữ liệu: ${err.message}`;
  });
