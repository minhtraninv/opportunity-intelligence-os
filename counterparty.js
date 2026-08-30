(() => {
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

  const fmtMoney = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return '—';
    if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toLocaleString('vi-VN', {maximumFractionDigits:2})} tỷ`;
    if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString('vi-VN', {maximumFractionDigits:1})} triệu`;
    return `${n.toLocaleString('vi-VN')} đ`;
  };

  const PATH_LABELS = {
    potential_prime_or_partner: 'Có thể prime / partner',
    subcontract_or_sourcing: 'Ưu tiên thầu phụ / sourcing',
    watch_only: 'Chỉ theo dõi',
  };

  function ensureSection(){
    if(document.getElementById('counterpartyDossierGrid')) return;
    const relationGrid = document.getElementById('relationshipGrid');
    const anchor = relationGrid || document.getElementById('partnerGrid');
    if(!anchor) return;
    anchor.insertAdjacentHTML('afterend', `
      <div class="section-head" style="margin-top:30px">
        <div><div class="eyebrow">COUNTERPARTY DOSSIERS · V1.5</div><h2>Từ historical winner tới người cần điều tra</h2></div>
        <span id="counterpartyStatus" class="muted">Đang dựng dossier…</span>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <strong>Nguyên tắc:</strong> hệ thống chỉ chọn counterparty từ bằng chứng award history. Contact từ MSC chỉ lấy field business-email đã whitelist và phải khớp đúng orgCode/taxCode. Website/email/phone ngoài MSC chỉ hiện khi có nguồn công khai xác minh; chưa đủ bằng chứng thì ghi <strong>UNRESOLVED</strong>.
      </div>
      <div id="counterpartyDossierGrid" class="buyer-grid"></div>`);
  }

  function mergeContacts(base, official){
    const all = [...(base || []), ...(official || [])];
    const seen = new Set();
    return all.filter(x => {
      const key = `${String(x.type || '').toLowerCase()}|${String(x.value || '').toLowerCase()}`;
      if(!x.value || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function contactBlock(counterparty){
    const contacts = counterparty.verified_contact_paths || [];
    if(!contacts.length){
      return `<div style="margin-top:8px;padding:8px 10px;border:1px solid var(--line);border-radius:10px">
        <div class="eyebrow">CONTACT · UNRESOLVED</div>
        <div class="muted small">Chưa có kênh liên hệ công khai đủ bằng chứng. Không suy đoán email/phone/person.</div>
      </div>`;
    }
    return `<div style="margin-top:8px;padding:8px 10px;border:1px solid var(--line);border-radius:10px">
      <div class="eyebrow">VERIFIED CONTACT PATHS</div>
      ${contacts.map(x => `<div class="muted small" style="margin-top:4px">
        <strong>${esc(x.type || 'contact')}:</strong> ${esc(x.value || '')}
        ${x.scope ? ` · ${esc(x.scope)}` : ''}
        ${x.source_url ? ` · <a href="${esc(safeUrl(x.source_url))}" target="_blank" rel="noopener noreferrer">nguồn</a>` : ''}
      </div>`).join('')}
      <div class="muted small" style="margin-top:6px">Verified contact chỉ xác nhận kênh công khai của đúng pháp nhân; không có nghĩa người nhận đang phụ trách gói hiện tại.</div>
    </div>`;
  }

  function counterpartyCard(counterparty, rank){
    const roles = (counterparty.target_roles_to_find || []).slice(0,3);
    const offers = (counterparty.offers_to_test || []).slice(0,3);
    const why = (counterparty.why_this_counterparty || []).slice(0,3);
    return `<div style="margin-top:10px;padding:11px;border:1px solid var(--line);border-radius:12px">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
        <div>
          <div class="eyebrow">TARGET #${rank}</div>
          <strong>${esc(counterparty.contractor_name)}</strong>
        </div>
        <span class="pill">Fit ${esc(counterparty.counterparty_score)}/100</span>
      </div>
      <div class="muted small" style="margin-top:6px">${why.map(x => esc(x)).join(' · ')}</div>
      <div style="margin-top:8px"><strong>Vai trò cần tìm:</strong> ${roles.map(x => esc(x)).join(' · ')}</div>
      <div style="margin-top:6px"><strong>Offer test:</strong> ${offers.map(x => esc(x)).join(' · ')}</div>
      <div class="muted small" style="margin-top:6px"><strong>First ask:</strong> ${esc(counterparty.first_ask)}</div>
      ${contactBlock(counterparty)}
      ${counterparty.evidence_url ? `<div class="evidence-links" style="margin-top:8px"><a href="${esc(safeUrl(counterparty.evidence_url))}" target="_blank" rel="noopener noreferrer">Mở KQLCNT chứng minh lịch sử</a></div>` : ''}
    </div>`;
  }

  function dossierCard(dossier){
    const counterparties = (dossier.counterparties || []).slice(0,3);
    return `<article class="buyer-card">
      <div class="eyebrow">${esc(dossier.tender_code)} · ${esc(PATH_LABELS[dossier.recommended_path] || dossier.recommended_path)}</div>
      <h3>${esc(dossier.buyer)}</h3>
      <div class="trigger">${esc(dossier.title)}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin:9px 0">
        <span class="pill">${esc(fmtMoney(dossier.package_price_vnd))}</span>
        <span class="pill">Prime ${esc(dossier.prime_fit_score)}/100</span>
        <span class="pill">Subcontract ${esc(dossier.subcontract_fit_score)}/100</span>
        <span class="pill">Còn ${esc(dossier.days_to_close == null ? '—' : `${Number(dossier.days_to_close).toFixed(1)} ngày`)}</span>
      </div>
      <div class="signal-evidence"><strong>First move:</strong> ${esc(dossier.recommended_first_move)}</div>
      ${counterparties.length ? counterparties.map((x,i) => counterpartyCard(x,i+1)).join('') : '<div class="muted small" style="margin-top:10px">Chưa có counterparty đủ evidence trong sample.</div>'}
      <div class="trigger" style="margin-top:10px"><strong>Success 48h:</strong> ${esc(dossier.success_signal_48h)}</div>
      <div class="risk" style="margin-top:8px"><strong>Kill 48h:</strong> ${esc(dossier.kill_signal_48h)}</div>
      ${dossier.official_source_url ? `<div class="evidence-links" style="margin-top:10px"><a href="${esc(safeUrl(dossier.official_source_url))}" target="_blank" rel="noopener noreferrer">Mở TBMT gốc</a></div>` : ''}
    </article>`;
  }

  Promise.all([
    fetch('data/counterparty_intelligence.json', {cache:'no-store'}).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch('data/official_contact_intelligence.json', {cache:'no-store'}).then(r => r.ok ? r.json() : null).catch(() => null),
  ]).then(([data, officialData]) => {
      if(!data) return;
      ensureSection();

      const officialByPartner = new Map((officialData?.contacts || []).map(x => [x.partner_id, x]));
      const dossiers = (data.dossiers || []).map(dossier => ({
        ...dossier,
        counterparties: (dossier.counterparties || []).map(counterparty => {
          const official = officialByPartner.get(counterparty.partner_id);
          const paths = mergeContacts(counterparty.verified_contact_paths, official?.contact_paths);
          return {
            ...counterparty,
            contact_status: paths.length ? 'verified' : 'unresolved',
            verified_contact_paths: paths,
          };
        }),
      }));

      const allTargets = dossiers.flatMap(x => x.counterparties || []);
      const verifiedTargets = allTargets.filter(x => (x.verified_contact_paths || []).length > 0).length;
      const verifiedPaths = allTargets.reduce((sum,x) => sum + (x.verified_contact_paths || []).length, 0);
      const unresolved = allTargets.length - verifiedTargets;

      const status = document.getElementById('counterpartyStatus');
      if(status){
        status.textContent = `${dossiers.length} dossier · ${allTargets.length} targets · ${verifiedTargets} targets có contact · ${verifiedPaths} verified paths · ${unresolved} unresolved`;
      }
      const grid = document.getElementById('counterpartyDossierGrid');
      if(!grid) return;
      const visible = dossiers
        .slice()
        .sort((a,b) => Number(b.subcontract_fit_score || 0) - Number(a.subcontract_fit_score || 0))
        .slice(0,8);
      grid.innerHTML = visible.length
        ? visible.map(dossierCard).join('')
        : '<div class="panel muted">Chưa có dossier vượt ngưỡng điều tra.</div>';
    })
    .catch(() => {});
})();
