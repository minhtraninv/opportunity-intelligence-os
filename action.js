(() => {
  const CATEGORY_LABELS = {
    digital_services: 'Digital / software',
    printing_media: 'In ấn / truyền thông',
    consulting: 'Tư vấn',
    maintenance: 'Bảo trì / facility',
    office_goods: 'Văn phòng / thiết bị',
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

  const PATH_LABELS = {
    potential_prime_or_partner: 'Có thể prime / partner',
    subcontract_or_sourcing: 'Ưu tiên thầu phụ / sourcing',
    watch_only: 'Chỉ theo dõi',
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

  const fmtMoney = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return 'Chưa rõ giá gói';
    if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toLocaleString('vi-VN', {maximumFractionDigits:2})} tỷ`;
    if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString('vi-VN', {maximumFractionDigits:1})} triệu`;
    return `${n.toLocaleString('vi-VN')} đ`;
  };

  function candidateRows(match){
    const candidates = (match?.candidates || []).slice(0,3);
    if(!candidates.length){
      return '<div class="muted small">Chưa có historical winner cùng nhóm đủ bằng chứng trong mẫu theo dõi.</div>';
    }
    return `<div style="margin-top:10px">
      <div class="eyebrow">HISTORICAL PRIME CANDIDATES</div>
      ${candidates.map(c => `<div style="margin-top:7px;padding:8px 10px;border:1px solid var(--line);border-radius:10px">
        <strong>${esc(c.contractor_name)}</strong>
        <div class="muted small">Match ${esc(c.match_score)}/100 · ${esc(c.observed_wins_same_category)} win quan sát cùng nhóm · win gần nhất ${esc(fmtDate(c.latest_win_at))}</div>
        ${c.latest_source_url ? `<div class="evidence-links" style="margin-top:5px"><a href="${esc(safeUrl(c.latest_source_url))}" target="_blank" rel="noopener noreferrer">Mở KQLCNT gần nhất</a></div>` : ''}
      </div>`).join('')}
      <div class="muted small" style="margin-top:6px">Đây là ứng viên điều tra dựa trên lịch sử thắng thầu, không phải bằng chứng họ đang dự gói hiện tại.</div>
    </div>`;
  }

  function executionDetails(brief){
    if(!brief) return '';
    const offers = (brief.offers_to_test || []).map(x => `<li>${esc(x)}</li>`).join('');
    const actions = (brief.actions_48h || []).map((x,i) => `<li><strong>${i+1}.</strong> ${esc(x)}</li>`).join('');
    return `<details style="margin-top:12px">
      <summary style="cursor:pointer;font-weight:700">Kế hoạch kiếm tiền / kiểm chứng 48 giờ</summary>
      <div style="margin-top:10px">
        <div class="muted small"><strong>Đường đi:</strong> ${esc(brief.route)}</div>
        <div class="muted small" style="margin-top:6px"><strong>Người cần điều tra:</strong> ${esc(brief.target_counterpart)}</div>
        <div style="margin-top:10px"><strong>Offer có thể test:</strong><ul>${offers}</ul></div>
        <div style="margin-top:10px"><strong>48 giờ:</strong><ol>${actions}</ol></div>
        <div class="trigger" style="margin-top:10px"><strong>Success signal:</strong> ${esc(brief.success_signal)}</div>
        <div class="risk" style="margin-top:8px"><strong>Kill:</strong> ${esc(brief.kill_signal)}</div>
        <div class="muted small" style="margin-top:8px"><strong>Evidence gap:</strong> ${esc(brief.evidence_gap)}</div>
      </div>
    </details>`;
  }

  function card(x, match, brief){
    const actionClass = x.action_level === 'investigate_now' ? 'official' : 'hypothesis';
    const angles = (x.small_capital_angles || []).slice(0,3);
    const closeText = x.days_to_close == null
      ? `Đóng thầu: ${fmtDate(x.closes_at)}`
      : `Còn ${Math.max(0, x.days_to_close).toFixed(1)} ngày`;
    const prime = x.prime_fit_score == null ? 'Chưa chấm' : `${x.prime_fit_score}/100`;
    const sub = x.subcontract_fit_score == null ? '—' : `${x.subcontract_fit_score}/100`;

    return `<article class="buyer-card">
      <div class="eyebrow">${esc(CATEGORY_LABELS[x.procurement_category] || x.procurement_category)}</div>
      <h3>${esc(x.buyer)}</h3>
      <div class="trigger"><strong>${esc(x.tender_code)}</strong> · ${esc(x.title)}</div>
      <div style="margin:10px 0;display:flex;gap:6px;flex-wrap:wrap">
        <span class="tag ${actionClass}">${esc(ACTION_LABELS[x.action_level] || x.action_level)}</span>
        <span class="pill">${esc(fmtMoney(x.package_price_vnd))}</span>
        <span class="pill">Prime fit ${esc(prime)}</span>
        <span class="pill">Subcontract fit ${esc(sub)}</span>
        <span class="pill up">${esc(PATH_LABELS[x.recommended_path] || x.recommended_path)}</span>
      </div>
      <div class="muted small">Đăng: ${esc(fmtDate(x.posted_at))} · ${esc(closeText)} · Buyer trigger ${esc(x.buyer_trigger_score)}/100</div>
      <ul>${angles.map(a => `<li>${esc(a)}</li>`).join('')}</ul>
      ${candidateRows(match)}
      ${executionDetails(brief)}
      <div class="muted small" style="margin-top:10px"><strong>Bước xác minh:</strong> ${esc(x.next_action)}</div>
      <div class="risk" style="margin-top:8px"><strong>Kill:</strong> ${esc(x.kill_criteria)}</div>
      <div class="evidence-links" style="margin-top:10px">
        <a href="${esc(safeUrl(x.official_verification_url || x.source_url))}" target="_blank" rel="noopener noreferrer">Mở TBMT trên MSC</a>
      </div>
    </article>`;
  }

  function partnerCard(p){
    const cats = (p.categories || []).slice(0,3).map(x => CATEGORY_LABELS[x] || x).join(' · ');
    const buyers = (p.buyers_observed || []).slice(0,3).join(' · ');
    return `<article class="buyer-card">
      <div class="eyebrow">OBSERVED PRIME / PARTNER</div>
      <h3>${esc(p.contractor_name)}</h3>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0">
        <span class="pill">Evidence ${esc(p.partner_evidence_score)}/100</span>
        <span class="pill">${esc(p.observed_wins)} win quan sát</span>
        <span class="pill">${esc(fmtMoney(p.observed_winning_value_vnd))} giá trị quan sát</span>
      </div>
      <div class="trigger"><strong>Nhóm:</strong> ${esc(cats || 'Chưa phân loại')}</div>
      <div class="muted small" style="margin-top:8px"><strong>Buyer từng quan sát:</strong> ${esc(buyers || '—')}</div>
      <div class="muted small" style="margin-top:6px"><strong>Win gần nhất:</strong> ${esc(p.latest_tender_title || '—')} · ${esc(fmtDate(p.latest_win_at))}</div>
      <div class="muted small" style="margin-top:8px">${esc(p.caveat)}</div>
      ${p.latest_source_url ? `<div class="evidence-links" style="margin-top:10px"><a href="${esc(safeUrl(p.latest_source_url))}" target="_blank" rel="noopener noreferrer">Mở bằng chứng KQLCNT</a></div>` : ''}
    </article>`;
  }

  Promise.all([
    fetch('data/action_intelligence.json', {cache:'no-store'}).then(r => {
      if(!r.ok) throw new Error(`action HTTP ${r.status}`);
      return r.json();
    }),
    fetch('data/partner_intelligence.json', {cache:'no-store'}).then(r => r.ok ? r.json() : null).catch(() => null),
  ])
    .then(([data, partnerData]) => {
      const coverage = data.coverage || {};
      const triggers = (data.buyer_triggers || [])
        .filter(x => ['investigate_now','watch'].includes(x.action_level))
        .slice(0,24);
      const matches = new Map((partnerData?.matches_by_open_tender || []).map(x => [x.tender_code, x]));
      const briefs = new Map((partnerData?.execution_briefs || []).map(x => [x.tender_code, x]));

      const count = document.getElementById('liveBuyerCount');
      if(count) count.textContent = coverage.investigate_now ?? triggers.length;

      const status = document.getElementById('buyerRadarStatus');
      if(status){
        status.textContent = `Live ${coverage.active_recent_tenders ?? 0} gói mở · ${coverage.investigate_now ?? 0} điều tra ngay · ${coverage.tbmt_detail_confirmed ?? 0} TBMT detail · ${coverage.source_errors_last_run ?? 0} lỗi nguồn`;
      }

      const dataStatus = document.getElementById('dataStatus');
      if(dataStatus && partnerData) dataStatus.textContent = 'V1.4 · ACTION INTELLIGENCE';

      const grid = document.getElementById('liveBuyerGrid');
      if(grid){
        grid.innerHTML = triggers.length
          ? triggers.map(x => card(x, matches.get(x.tender_code), briefs.get(x.tender_code))).join('')
          : '<div class="panel muted">Chưa có buyer trigger đủ điểm. Đây là trạng thái hợp lệ; hệ thống không ép phải tìm ra “cơ hội” mỗi lần chạy.</div>';
      }

      const partnerStatus = document.getElementById('partnerRadarStatus');
      const partnerGrid = document.getElementById('partnerGrid');
      if(partnerData){
        const pc = partnerData.coverage || {};
        if(partnerStatus){
          partnerStatus.textContent = `${pc.unique_partner_candidates ?? 0} historical winners · ${pc.open_tenders_with_partner_candidates ?? 0} gói mở có candidate · ${pc.source_errors_last_run ?? 0} lỗi nguồn`;
        }
        if(partnerGrid){
          const partners = (partnerData.partner_candidates || []).slice(0,12);
          partnerGrid.innerHTML = partners.length
            ? partners.map(partnerCard).join('')
            : '<div class="panel muted">Chưa đủ KQLCNT để dựng Partner Radar. Pipeline sẽ tích lũy qua các lần chạy.</div>';
        }
      } else {
        if(partnerStatus) partnerStatus.textContent = 'Partner Radar đang tích lũy KQLCNT.';
        if(partnerGrid) partnerGrid.innerHTML = '<div class="panel muted">Chưa có partner_intelligence.json. Buyer Radar vẫn hoạt động độc lập.</div>';
      }
    })
    .catch(err => {
      const count = document.getElementById('liveBuyerCount');
      if(count) count.textContent = '—';
      const status = document.getElementById('buyerRadarStatus');
      if(status) status.textContent = `Procurement Radar chưa có dữ liệu: ${err.message}`;
      const grid = document.getElementById('liveBuyerGrid');
      if(grid) grid.innerHTML = '<div class="panel muted">Pipeline Action Intelligence chưa sinh dữ liệu hoặc GitHub Pages chưa deploy bản mới.</div>';
    });
})();
