(() => {
  'use strict';

  const anchor = document.getElementById('attentionAnchor');
  if(!anchor) return;
  let section = document.getElementById('frontierSection');
  if(!section){
    section = document.createElement('section');
    section.id = 'frontierSection';
    section.innerHTML = `<div class="section-head overview-section"><div class="overview-section-copy"><div class="eyebrow">DISCOVERY FRONTIER · STRUCTURED SERENDIPITY</div><h2>Ngoài vùng quen thuộc, điều gì đang đổi đáng để mở hồ sơ?</h2><p class="muted">Tối đa vài candidate từ attention/distribution, technology capability, behavior, talent và revealed capital/ownership footprints. Discovery rộng, kết luận vẫn hẹp.</p></div><span id="frontierStatus" class="muted">Đang quét frontier…</span></div><div id="frontierOverview" class="overview-grid"></div><div id="frontierMissNote" class="overview-radar-note" style="margin-top:12px"></div>`;
    anchor.insertAdjacentElement('afterend', section);
  }
  const target = document.getElementById('frontierOverview');
  const status = document.getElementById('frontierStatus');
  const missNote = document.getElementById('frontierMissNote');
  if(!target) return;

  const SHIFT_LABELS = {
    attention_distribution: 'Attention / Distribution',
    technology_frontier: 'Technology Capability',
    capital_ownership: 'Capital / Ownership',
    behavior_change: 'Behavior Change',
    talent_migration: 'Talent Migration'
  };

  const esc = value => String(value ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');

  const fmtDate = value => {
    if(!value) return '—';
    const dt = new Date(value);
    if(Number.isNaN(dt.getTime())) return esc(value);
    return dt.toLocaleDateString('vi-VN', {day:'2-digit',month:'2-digit',year:'numeric'});
  };

  const tag = (text, klass='hypothesis') => `<span class="tag ${klass}">${esc(text)}</span>`;

  function evidenceBlock(rows){
    if(!Array.isArray(rows) || !rows.length) return '';
    const body = rows.map(row => {
      const url = String(row?.source_url || '');
      const title = esc(row?.title || 'Nguồn discovery');
      const link = /^https?:\/\//.test(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${title}</a>` : title;
      return `<div class="evidence-row">${link}<div class="evidence-meta">${esc(row?.publisher || '—')} · ${fmtDate(row?.published_at)} · discovery-only</div></div>`;
    }).join('');
    return `<details class="evidence-drilldown"><summary>${rows.length} manh mối discovery phía sau</summary><div class="evidence-audit-body">${body}</div></details>`;
  }

  function card(row){
    const shifts = (row.shift_types || []).map(x => tag(SHIFT_LABELS[x] || x)).join(' ');
    const state = row.state === 'investigate' ? 'INVESTIGATE' : 'WATCH';
    const question = row.questions?.[0] || 'Có structural change thật sự ở đây hay chỉ là một headline nổi bật?';
    const scope = row.vietnam_relevance ? 'Việt Nam relevance' : 'Global surprise';
    return `<article class="panel overview-card overview-opportunity frontier-card">
      <div class="overview-kicker">${esc(state)} · score ${esc(row.score)} · ${esc(scope)}</div>
      <h3>${esc(row.label || 'Discovery candidate')}</h3>
      <div class="frontier-tags">${shifts}</div>
      <p>${esc(row.why_now || '')}</p>
      <div class="attention-question"><strong>Câu hỏi nên mở:</strong> ${esc(question)}</div>
      <div class="card-footer muted small">${esc(row.source_count || 0)} nguồn · ${esc(row.evidence_count || 0)} evidence · seen ${fmtDate(row.first_seen_at)} → ${fmtDate(row.last_seen_at)}</div>
      ${evidenceBlock(row.evidence)}
    </article>`;
  }

  async function load(){
    try {
      const response = await fetch('data/frontier_intelligence.json');
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const queue = Array.isArray(data.attention_queue) ? data.attention_queue.slice(0,4) : [];
      const coverage = data.coverage || {};
      const healthy = coverage.healthy_frontier_sources ?? 0;
      const configured = coverage.configured_frontier_sources ?? 0;
      if(status) status.textContent = `${healthy}/${configured} frontier feeds khỏe · discovery-only`;

      if(queue.length){
        target.innerHTML = queue.map(card).join('');
      } else {
        target.innerHTML = '<article class="panel overview-card"><div class="overview-kicker">NO FORCED STORY</div><h3>Chưa có frontier candidate đủ ngưỡng</h3><p class="muted">Đây là trạng thái hợp lệ. Hệ thống không buộc phải tạo một “trend mới” mỗi ngày.</p></article>';
      }

      const misses = Array.isArray(data.miss_benchmarks) ? data.miss_benchmarks : [];
      const debt = misses.filter(x => x.status === 'coverage_debt');
      const detectable = misses.filter(x => x.status === 'detectable_now');
      if(missNote){
        if(debt.length){
          missNote.innerHTML = `<strong>Miss learning:</strong> ${esc(debt.length)} benchmark vẫn là coverage debt. Hệ thống giữ chúng như bài kiểm tra “đáng lẽ phải có cơ hội nhìn thấy”, không hardcode kết luận.`;
        } else if(detectable.length){
          missNote.innerHTML = `<strong>Miss learning:</strong> ${esc(detectable.length)} benchmark cũ hiện đã có đường discovery. Detectable ≠ thesis đúng; chỉ có nghĩa blind spot đã giảm.`;
        } else {
          missNote.textContent = 'Miss Log chưa có benchmark đang hoạt động.';
        }
      }
    } catch(err) {
      console.error('Frontier intelligence unavailable', err);
      if(status) status.textContent = 'Frontier data chưa sẵn sàng';
      target.innerHTML = '<article class="panel overview-card overview-warning"><h3>Discovery Frontier chưa có dữ liệu</h3><p class="muted">Core radar vẫn hoạt động bình thường; frontier là lớp mở rộng sight và không được phép làm hỏng baseline chính.</p></article>';
      if(missNote) missNote.textContent = 'Frontier failure không được nâng thành signal hay conclusion.';
    }
  }

  load();
})();
