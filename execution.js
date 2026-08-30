(() => {
  const STORAGE_KEY = 'oi.execution.v1';
  const STAGES = [
    ['ready_to_research', 'Sẵn sàng'],
    ['contacted', 'Đã liên hệ'],
    ['replied', 'Có phản hồi'],
    ['qualified', 'Qualified'],
    ['dead', 'Dead'],
  ];

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

  function loadState(){
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}; }
    catch { return {}; }
  }

  function saveState(state){
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function ensureSection(){
    let grid = document.getElementById('executionQueue');
    if(grid) return grid;
    const actionQueue = document.getElementById('actionQueue');
    const hero = document.querySelector('#today .hero-grid');
    const anchor = actionQueue || hero;
    if(!anchor) return null;
    const html = `
      <div id="executionQueueHead" class="section-head" style="margin-top:28px">
        <div><div class="eyebrow">EXECUTION LOOP · V1.6</div><h2>Outreach đã đủ bằng chứng để thử</h2></div>
        <span id="executionQueueStatus" class="muted">Đang dựng execution packs…</span>
      </div>
      <div class="panel" style="margin-bottom:14px">
        <strong>Human-in-the-loop:</strong> hệ thống không tự gửi. Draft chỉ được copy khi bạn nhập bằng chứng năng lực thật. Một historical winner không được mô tả như bidder hiện tại.
      </div>
      <div id="executionQueue" class="signal-grid"></div>`;
    if(actionQueue){
      actionQueue.insertAdjacentHTML('afterend', html);
    } else {
      hero.insertAdjacentHTML('afterend', html);
    }
    return document.getElementById('executionQueue');
  }

  function contactHtml(paths){
    return (paths || []).map(x => `
      <div class="muted small" style="margin-top:4px">
        <strong>${esc(x.type || 'contact')}:</strong> ${esc(x.value)}
        ${x.scope ? ` · ${esc(x.scope)}` : ''}
        ${x.source_url ? ` · <a href="${esc(safeUrl(x.source_url))}" target="_blank" rel="noopener noreferrer">nguồn</a>` : ''}
      </div>`).join('');
  }

  function packCard(pack, state){
    const local = state[pack.id] || {};
    const stage = local.stage || pack.default_stage || 'ready_to_research';
    const proof = local.capabilityProof || '';
    const note = local.note || '';
    const historical = pack.historical_evidence || {};
    return `<article class="signal-card execution-pack" data-pack-id="${esc(pack.id)}">
      <div class="signal-top">
        <div>
          <div class="eyebrow">PRIORITY ${esc(pack.priority_score)}/100 · ${esc(stage.toUpperCase())}</div>
          <div class="signal-title">${esc(pack.contractor_name)}</div>
          <div class="signal-meta">
            <span class="pill">${esc(pack.tender_code)}</span>
            <span class="pill">${esc(pack.buyer)}</span>
            <span class="pill">Còn ${esc(pack.days_to_close == null ? '—' : `${Number(pack.days_to_close).toFixed(1)} ngày`)}</span>
          </div>
        </div>
        <div class="signal-score hot">${esc(pack.priority_score)}</div>
      </div>

      <div class="signal-why"><strong>Offer cần kiểm chứng:</strong> ${esc(pack.offer_to_validate || '—')}</div>
      <div class="signal-evidence"><strong>Bằng chứng lịch sử:</strong> ${esc(historical.latest_win_title || '—')} · ${esc(historical.observed_wins_same_category || 0)} win cùng nhóm quan sát.</div>
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
      <textarea class="execution-proof" rows="3" placeholder="Ví dụ: dự án đã làm, partner thực hiện thật, thiết bị/nhân sự đang có, rate card…">${esc(proof)}</textarea>
      <label style="display:block;margin-top:8px;font-weight:700">Ghi chú kết quả</label>
      <textarea class="execution-note" rows="2" placeholder="Ai phản hồi? Hỏi gì? Lý do từ chối?">${esc(note)}</textarea>

      <div class="button-row execution-stages" style="margin-top:9px;flex-wrap:wrap">
        ${STAGES.map(([value,label]) => `<button class="btn ${stage === value ? 'secondary' : 'ghost'} execution-stage" data-stage="${value}">${label}</button>`).join('')}
        <button class="btn secondary execution-copy">Sao chép draft</button>
      </div>
      <div class="muted small execution-message" style="margin-top:7px"></div>
      <div class="evidence-links" style="margin-top:8px">
        ${pack.official_tender_url ? `<a href="${esc(safeUrl(pack.official_tender_url))}" target="_blank" rel="noopener noreferrer">TBMT hiện tại</a>` : ''}
        ${historical.latest_evidence_url ? `<a href="${esc(safeUrl(historical.latest_evidence_url))}" target="_blank" rel="noopener noreferrer">KQLCNT lịch sử</a>` : ''}
      </div>
    </article>`;
  }

  function bindInteractions(packs){
    const byId = new Map(packs.map(x => [x.id, x]));
    document.querySelectorAll('.execution-pack').forEach(card => {
      const id = card.dataset.packId;
      const pack = byId.get(id);
      if(!pack) return;

      const persist = (patch) => {
        const state = loadState();
        state[id] = {...(state[id] || {}), ...patch, updatedAt:new Date().toISOString()};
        saveState(state);
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
        const capability = (proof?.value || '').trim();
        const msg = card.querySelector('.execution-message');
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

  fetch('data/outreach_intelligence.json', {cache:'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if(!data) return;
      const grid = ensureSection();
      if(!grid) return;
      const state = loadState();
      const packs = (data.packs || []).slice(0,3);
      grid.innerHTML = packs.length
        ? packs.map(x => packCard(x,state)).join('')
        : '<div class="panel muted">Chưa có outreach pack nào vượt đủ evidence gates. Hệ thống không ép tạo lead giả.</div>';
      const status = document.getElementById('executionQueueStatus');
      const c = data.coverage || {};
      if(status) status.textContent = `${c.outreach_packs_ready ?? 0} packs ready · ${c.unique_counterparties_ready ?? 0} counterparties · ${c.verified_contact_paths_in_ready_packs ?? 0} verified paths`;
      bindInteractions(packs);
    })
    .catch(() => {});
})();
