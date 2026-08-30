(() => {
  const CATEGORY_LABELS = {
    digital_services: 'Digital / software',
    printing_media: 'In ấn / truyền thông',
    consulting: 'Tư vấn',
    maintenance: 'Bảo trì / facility',
    office_goods: 'Văn phòng / thiết bị nhỏ',
    garment_ppe: 'Đồng phục / PPE',
    food_services: 'Thực phẩm / suất ăn',
    logistics: 'Logistics',
    medical: 'Y tế',
    machinery: 'Máy móc / phụ tùng',
    construction: 'Xây dựng',
    other: 'Khác',
  };

  const ACTION_LABELS = {
    investigate_now: 'ĐIỀU TRA NGAY',
    watch: 'THEO DÕI',
    context: 'THAM CHIẾU',
    too_late: 'QUÁ SÁT HẠN',
    closed: 'ĐÃ ĐÓNG',
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
    if (!iso) return '—';
    try {
      return new Intl.DateTimeFormat('vi-VN', {dateStyle:'short', timeStyle:'short'}).format(new Date(iso));
    } catch {
      return iso;
    }
  };

  function card(x){
    const actionClass = x.action_level === 'investigate_now' ? 'official' : 'hypothesis';
    const angles = (x.small_capital_angles || []).slice(0,3);
    const closeText = x.days_to_close == null
      ? `Đóng thầu: ${fmtDate(x.closes_at)}`
      : `Còn ${Math.max(0, x.days_to_close).toFixed(1)} ngày`;

    return `<article class="buyer-card">
      <div class="eyebrow">${esc(CATEGORY_LABELS[x.procurement_category] || x.procurement_category)}</div>
      <h3>${esc(x.buyer)}</h3>
      <div class="trigger"><strong>${esc(x.tender_code)}</strong> · ${esc(x.title)}</div>
      <div style="margin:10px 0;display:flex;gap:6px;flex-wrap:wrap">
        <span class="tag ${actionClass}">${esc(ACTION_LABELS[x.action_level] || x.action_level)}</span>
        <span class="pill">Buyer trigger ${esc(x.buyer_trigger_score)}/100</span>
        <span class="pill">Small-cap fit ${esc(x.small_capital_fit_score)}/100</span>
        ${x.direct_private ? '<span class="pill up">Gói trực tiếp</span>' : ''}
      </div>
      <div class="muted small">Đăng: ${esc(fmtDate(x.posted_at))} · ${esc(closeText)}</div>
      <ul>${angles.map(a => `<li>${esc(a)}</li>`).join('')}</ul>
      <div class="muted small"><strong>Bước kế:</strong> ${esc(x.next_action)}</div>
      <div class="risk" style="margin-top:8px"><strong>Kill:</strong> ${esc(x.kill_criteria)}</div>
      <div class="evidence-links" style="margin-top:10px">
        <a href="${esc(safeUrl(x.source_url))}" target="_blank" rel="noopener noreferrer">Mở discovery source</a>
        <a href="${esc(safeUrl(x.official_verification_url))}" target="_blank" rel="noopener noreferrer">Xác minh trên MSC</a>
      </div>
    </article>`;
  }

  fetch('data/action_intelligence.json', {cache:'no-store'})
    .then(r => {
      if(!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      const coverage = data.coverage || {};
      const triggers = (data.buyer_triggers || [])
        .filter(x => ['investigate_now','watch'].includes(x.action_level))
        .slice(0,24);

      const count = document.getElementById('liveBuyerCount');
      if(count) count.textContent = coverage.investigate_now ?? triggers.length;

      const status = document.getElementById('buyerRadarStatus');
      if(status){
        status.textContent = `Live ${coverage.active_tenders ?? 0} gói · ${coverage.investigate_now ?? 0} cần điều tra · ${coverage.source_errors_last_run ?? 0} lỗi nguồn`;
      }

      const grid = document.getElementById('liveBuyerGrid');
      if(grid){
        grid.innerHTML = triggers.length
          ? triggers.map(card).join('')
          : '<div class="panel muted">Chưa có buyer trigger đủ điểm. Đây là trạng thái hợp lệ; hệ thống không ép phải tìm ra “cơ hội” mỗi lần chạy.</div>';
      }
    })
    .catch(err => {
      const count = document.getElementById('liveBuyerCount');
      if(count) count.textContent = '—';
      const status = document.getElementById('buyerRadarStatus');
      if(status) status.textContent = `Procurement Radar chưa có dữ liệu: ${err.message}`;
      const grid = document.getElementById('liveBuyerGrid');
      if(grid) grid.innerHTML = '<div class="panel muted">Pipeline V1.3 chưa sinh action_intelligence.json hoặc GitHub Pages chưa deploy bản mới.</div>';
    });
})();
