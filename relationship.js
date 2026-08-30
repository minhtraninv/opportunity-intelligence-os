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

  function ensureRelationshipSection(){
    if(document.getElementById('relationshipGrid')) return;
    const partnerGrid = document.getElementById('partnerGrid');
    if(!partnerGrid) return;
    partnerGrid.insertAdjacentHTML('afterend', `
      <div class="section-head" style="margin-top:30px">
        <div><div class="eyebrow">RELATIONSHIP INTELLIGENCE · V1.4.1</div><h2>Buyer ↔ vendor history trong mẫu KQLCNT</h2></div>
        <span id="relationshipStatus" class="muted">Đang ghép lịch sử buyer-vendor…</span>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <strong>Cách đọc:</strong> lặp lại buyer-vendor là dấu vết về kênh bán hàng và cạnh tranh trong sample đã thu. Nó <strong>không chứng minh ưu ái, thông đồng, bidder hiện tại hay khả năng thắng tương lai</strong>.
      </div>
      <div id="openRelationshipGrid" class="buyer-grid"></div>
      <div class="section-head" style="margin-top:22px">
        <div><div class="eyebrow">OBSERVED REPEAT EDGES</div><h2>Quan hệ lặp lại đáng nghiên cứu</h2></div>
        <span class="muted">Chỉ hiển thị evidence công khai; sample còn đang tích lũy.</span>
      </div>
      <div id="relationshipGrid" class="buyer-grid"></div>`);
  }

  function openMatchCard(match){
    const best = (match.same_buyer_candidates || [])[0];
    const sameCat = best?.same_category;
    return `<article class="buyer-card">
      <div class="eyebrow">CURRENT BUYER CHANNEL CHECK</div>
      <h3>${esc(match.buyer)}</h3>
      <div class="trigger"><strong>${esc(match.tender_code)}</strong> · ${esc(match.category)}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0">
        <span class="pill up">${esc(PATH_LABELS[match.recommended_path] || match.recommended_path)}</span>
        <span class="pill">${esc(match.relationship_route)}</span>
      </div>
      <div class="muted small">${esc(match.relationship_note)}</div>
      ${best ? `<div style="margin-top:10px;padding:10px;border:1px solid var(--line);border-radius:10px">
        <strong>${esc(best.contractor_name)}</strong>
        <div class="muted small">Cùng buyer: ${esc(best.same_buyer_observed_awards)} award quan sát · cùng category: ${esc(best.same_buyer_same_category_awards)} · relation match ${esc(best.relationship_match_score)}/100</div>
        <div class="muted small">${sameCat ? 'Có history cùng buyer + cùng loại nhu cầu.' : 'Có history với buyer nhưng khác loại nhu cầu.'}</div>
        ${best.latest_source_url ? `<div class="evidence-links" style="margin-top:6px"><a href="${esc(safeUrl(best.latest_source_url))}" target="_blank" rel="noopener noreferrer">Mở KQLCNT làm bằng chứng</a></div>` : ''}
      </div>` : '<div class="muted small" style="margin-top:8px">Chưa thấy same-buyer vendor trong sample hiện tại.</div>'}
    </article>`;
  }

  function edgeCard(edge){
    const cats = (edge.categories || []).slice(0,3).join(' · ');
    return `<article class="buyer-card">
      <div class="eyebrow">${esc(edge.relationship_signal === 'repeated_observed_awards' ? 'REPEATED EDGE' : 'OBSERVED EDGE')}</div>
      <h3>${esc(edge.buyer)}</h3>
      <div class="trigger"><strong>Vendor:</strong> ${esc(edge.contractor_name)}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0">
        <span class="pill">Evidence ${esc(edge.relationship_evidence_score)}/100</span>
        <span class="pill">${esc(edge.observed_awards)} award quan sát</span>
        <span class="pill">${esc(fmtMoney(edge.observed_award_value_vnd))}</span>
      </div>
      <div class="muted small"><strong>Nhóm:</strong> ${esc(cats || '—')}</div>
      <div class="muted small" style="margin-top:6px"><strong>Gần nhất:</strong> ${esc(edge.latest_tender_title || '—')} · ${esc(fmtDate(edge.latest_award_at))}</div>
      <div class="muted small" style="margin-top:8px">${esc(edge.caveat)}</div>
      ${edge.latest_source_url ? `<div class="evidence-links" style="margin-top:10px"><a href="${esc(safeUrl(edge.latest_source_url))}" target="_blank" rel="noopener noreferrer">Mở bằng chứng KQLCNT</a></div>` : ''}
    </article>`;
  }

  function relationshipMap(data){
    return new Map((data?.open_tender_relationships || []).map(x => [x.tender_code, x]));
  }

  function partnerMap(data){
    return new Map((data?.matches_by_open_tender || []).map(x => [x.tender_code, x]));
  }

  function actionPriority(trigger, partnerMatch, relationshipMatch){
    let score = Number(trigger.buyer_trigger_score || 0);
    score += Number(trigger.subcontract_fit_score || 0) * 0.18;
    if(trigger.tbmt_detail_confirmed) score += 5;
    const days = Number(trigger.days_to_close);
    if(Number.isFinite(days) && days >= 4 && days <= 14) score += 7;

    const bestPartner = partnerMatch?.candidates?.[0];
    if(bestPartner) score += 5 + Number(bestPartner.match_score || 0) * 0.05;
    if(trigger.recommended_path === 'subcontract_or_sourcing') score += 4;

    const sameBuyer = relationshipMatch?.same_buyer_candidates?.[0];
    if(sameBuyer?.same_category){
      if(trigger.recommended_path === 'subcontract_or_sourcing'){
        score += 8 + Number(sameBuyer.relationship_match_score || 0) * 0.04;
      } else if(trigger.recommended_path === 'potential_prime_or_partner'){
        score -= 5;
      }
    }
    return Math.round(score);
  }

  function enhancedQueueCard(trigger, partnerMatch, relationshipMatch, brief, rank){
    const bestPartner = partnerMatch?.candidates?.[0];
    const sameBuyer = relationshipMatch?.same_buyer_candidates?.[0];
    const firstOffer = brief?.offers_to_test?.[0] || trigger.small_capital_angles?.[0] || 'Đọc HSMT để tìm phần việc tách được.';
    const firstAction = brief?.actions_48h?.[0] || trigger.next_action;
    const relationshipLine = sameBuyer
      ? `${sameBuyer.contractor_name} · ${sameBuyer.same_buyer_observed_awards} award với buyer · ${sameBuyer.same_buyer_same_category_awards} cùng category`
      : 'chưa có same-buyer history trong sample';

    return `<article class="signal-card">
      <div class="signal-top">
        <div>
          <div class="eyebrow">PRIORITY #${rank} · RELATIONSHIP-AWARE</div>
          <div class="signal-title">${esc(trigger.buyer)}</div>
          <div class="signal-meta">
            <span class="pill up">${esc(PATH_LABELS[trigger.recommended_path] || trigger.recommended_path)}</span>
            <span class="pill">Còn ${esc(trigger.days_to_close == null ? '—' : `${Math.max(0, trigger.days_to_close).toFixed(1)} ngày`)}</span>
          </div>
        </div>
        <div class="signal-score hot">${esc(actionPriority(trigger, partnerMatch, relationshipMatch))}</div>
      </div>
      <div class="signal-why"><strong>${esc(trigger.tender_code)}</strong> · ${esc(trigger.title)}</div>
      <div class="signal-evidence"><strong>Offer test:</strong> ${esc(firstOffer)}</div>
      <div class="signal-evidence"><strong>Việc đầu tiên:</strong> ${esc(firstAction)}</div>
      <div class="signal-evidence"><strong>Historical prime candidate:</strong> ${esc(bestPartner ? `${bestPartner.contractor_name} · match ${bestPartner.match_score}/100` : 'chưa có')}</div>
      <div class="signal-evidence"><strong>Same-buyer history:</strong> ${esc(relationshipLine)}</div>
      <div class="muted small" style="margin-top:7px">${esc(relationshipMatch?.relationship_note || 'Relationship sample chưa có thêm bằng chứng cho gói này.')}</div>
      <div class="evidence-links"><a href="${esc(safeUrl(trigger.official_verification_url || trigger.source_url))}" target="_blank" rel="noopener noreferrer">Mở TBMT gốc</a></div>
    </article>`;
  }

  function enrichBuyerCards(relMap){
    const cards = [...document.querySelectorAll('#liveBuyerGrid .buyer-card')];
    for(const [tenderCode, match] of relMap.entries()){
      const card = cards.find(x => x.textContent.includes(tenderCode));
      if(!card || card.querySelector('.relationship-enrichment')) continue;
      const best = (match.same_buyer_candidates || [])[0];
      const html = `<div class="relationship-enrichment" style="margin-top:10px;padding:9px 10px;border:1px solid var(--line);border-radius:10px">
        <div class="eyebrow">SAME-BUYER HISTORY</div>
        <div class="muted small">${esc(match.relationship_note)}</div>
        ${best ? `<div style="margin-top:5px"><strong>${esc(best.contractor_name)}</strong> · ${esc(best.same_buyer_observed_awards)} award với buyer · ${esc(best.same_buyer_same_category_awards)} cùng category</div>` : '<div class="muted small" style="margin-top:5px">Chưa có candidate trong sample.</div>'}
      </div>`;
      const details = card.querySelector('details');
      if(details) details.insertAdjacentHTML('beforebegin', html);
      else card.insertAdjacentHTML('beforeend', html);
    }
  }

  function waitForBaseUI(callback, tries = 0){
    if(document.getElementById('actionQueue') && document.getElementById('liveBuyerGrid')){
      callback();
      return;
    }
    if(tries < 20) setTimeout(() => waitForBaseUI(callback, tries + 1), 250);
  }

  Promise.all([
    fetch('data/action_intelligence.json', {cache:'no-store'}).then(r => r.ok ? r.json() : null),
    fetch('data/partner_intelligence.json', {cache:'no-store'}).then(r => r.ok ? r.json() : null),
    fetch('data/relationship_intelligence.json', {cache:'no-store'}).then(r => r.ok ? r.json() : null),
  ]).then(([actionData, partnerData, relationshipData]) => {
    if(!relationshipData) return;

    ensureRelationshipSection();
    const coverage = relationshipData.coverage || {};
    const status = document.getElementById('relationshipStatus');
    if(status){
      status.textContent = `${coverage.buyer_vendor_edges ?? 0} buyer-vendor edges · ${coverage.repeated_edges ?? 0} lặp lại · ${coverage.open_tenders_with_same_buyer_same_category_history ?? 0} gói mở có same-buyer + same-category history`;
    }

    const currentGrid = document.getElementById('openRelationshipGrid');
    if(currentGrid){
      const current = (relationshipData.open_tender_relationships || [])
        .filter(x => (x.same_buyer_candidates || []).length)
        .sort((a,b) => Number(b.same_buyer_candidates?.[0]?.relationship_match_score || 0) - Number(a.same_buyer_candidates?.[0]?.relationship_match_score || 0))
        .slice(0,8);
      currentGrid.innerHTML = current.length
        ? current.map(openMatchCard).join('')
        : '<div class="panel muted">Chưa có gói mở trùng buyer với award history trong sample. Đây là thiếu dữ liệu, không phải bằng chứng buyer không có vendor cũ.</div>';
    }

    const grid = document.getElementById('relationshipGrid');
    if(grid){
      const edges = (relationshipData.relationship_edges || [])
        .filter(x => Number(x.observed_awards || 0) >= 2)
        .slice(0,10);
      grid.innerHTML = edges.length
        ? edges.map(edgeCard).join('')
        : '<div class="panel muted">Sample hiện chưa đủ quan hệ lặp lại. Hệ thống sẽ tích lũy theo các lần chạy.</div>';
    }

    waitForBaseUI(() => {
      const relMap = relationshipMap(relationshipData);
      enrichBuyerCards(relMap);

      if(!actionData || !partnerData) return;
      const pMap = partnerMap(partnerData);
      const briefs = new Map((partnerData.execution_briefs || []).map(x => [x.tender_code, x]));
      const triggers = (actionData.buyer_triggers || [])
        .filter(x => x.action_level === 'investigate_now')
        .map(trigger => ({
          trigger,
          partnerMatch: pMap.get(trigger.tender_code),
          relationshipMatch: relMap.get(trigger.tender_code),
          brief: briefs.get(trigger.tender_code),
        }))
        .sort((a,b) => actionPriority(b.trigger,b.partnerMatch,b.relationshipMatch) - actionPriority(a.trigger,a.partnerMatch,a.relationshipMatch))
        .slice(0,3);

      const queue = document.getElementById('actionQueue');
      if(queue && triggers.length){
        queue.innerHTML = triggers.map((x,i) => enhancedQueueCard(x.trigger,x.partnerMatch,x.relationshipMatch,x.brief,i+1)).join('');
      }
      const queueStatus = document.getElementById('actionQueueStatus');
      if(queueStatus){
        const sameBuyer = triggers.filter(x => x.relationshipMatch?.same_buyer_candidates?.[0]?.same_category).length;
        queueStatus.textContent = `${triggers.length} nhiệm vụ · ${sameBuyer} có same-buyer + same-category history · score là ưu tiên hành động, không phải xác suất thắng`;
      }
    });
  }).catch(() => {
    // Relationship layer is intentionally fail-soft; base Action Intelligence remains usable.
  });
})();
