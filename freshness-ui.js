(() => {
  'use strict';

  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');

  const LABEL = {macro:'Macro', regional:'Regional', contradiction:'Counter-signal'};
  const STATE = {
    fresh: 'FRESH',
    aging: 'AGING',
    stale: 'STALE',
    unknown: 'UNKNOWN'
  };

  function datasetLine(key, row){
    const age = row?.age_days == null ? 'không rõ tuổi' : `${row.age_days} ngày tuổi`;
    return `${LABEL[key] || key}: ${STATE[row?.status] || 'UNKNOWN'} · ${age}`;
  }

  function ensureBanner(){
    let node = document.getElementById('freshnessBanner');
    if(node) return node;
    const anchor = document.getElementById('attentionAnchor');
    if(!anchor) return null;
    node = document.createElement('div');
    node.id = 'freshnessBanner';
    node.className = 'overview-radar-note';
    anchor.insertAdjacentElement('beforebegin', node);
    return node;
  }

  function ensureSidebarMetric(){
    if(document.getElementById('snapshotFreshnessSidebar')) return;
    const errorMetric = document.getElementById('coverageErrorsSidebar')?.closest('.metric-row');
    if(!errorMetric) return;
    errorMetric.insertAdjacentHTML('afterend', '<div class="metric-row"><span>Snapshot current</span><strong id="snapshotFreshnessSidebar">—</strong></div>');
  }

  function staleMessage(label, row){
    const age = row?.age_days == null ? 'không xác định được tuổi' : `${row.age_days} ngày tuổi`;
    return `<article class="panel overview-card overview-warning"><div class="overview-kicker">STALE SNAPSHOT · KHÔNG DÙNG CHO CURRENT VIEW</div><h3>${esc(label)}</h3><p>Dữ liệu verified hiện ${esc(age)} và đã vượt cửa sổ current intelligence. Snapshot cũ vẫn được giữ làm historical context nhưng không được phép nâng conviction, regional state hoặc phản chứng hiện tại.</p></article>`;
  }

  function replaceIfStale(id, label, row){
    if(row?.status !== 'stale') return;
    const root = document.getElementById(id);
    if(!root) return;
    if(root.querySelector('[data-freshness-stale="1"]')) return;
    root.innerHTML = `<div data-freshness-stale="1">${staleMessage(label, row)}</div>`;
  }

  function observeStale(id, label, row){
    if(row?.status !== 'stale') return;
    const root = document.getElementById(id);
    if(!root) return;
    replaceIfStale(id, label, row);
    const observer = new MutationObserver(() => replaceIfStale(id, label, row));
    observer.observe(root, {childList:true, subtree:false});
  }

  fetch('data/freshness_state.json', {cache:'no-store'})
    .then(r => { if(!r.ok) throw new Error(`freshness HTTP ${r.status}`); return r.json(); })
    .then(payload => {
      const d = payload?.datasets || {};
      ensureSidebarMetric();
      const rows = ['macro','regional','contradiction'].map(k => d[k] || {status:'unknown'});
      const allFresh = rows.every(x => x.status === 'fresh');
      const anyStale = rows.some(x => x.status === 'stale');
      const anyUnknown = rows.some(x => !x.status || x.status === 'unknown');
      const banner = ensureBanner();
      if(banner){
        const detail = ['macro','regional','contradiction'].map(k => datasetLine(k,d[k])).join(' · ');
        if(anyStale){
          banner.innerHTML = `<strong>Freshness gate đang hạ quyền dữ liệu quá hạn.</strong> ${esc(detail)}. Snapshot STALE chỉ còn là historical context.`;
        } else if(anyUnknown){
          banner.innerHTML = `<strong>Không xác định đủ freshness.</strong> ${esc(detail)}. Dataset UNKNOWN không được phép tạo directional conviction.`;
        } else {
          banner.innerHTML = `<strong>Snapshot health:</strong> ${esc(detail)}. ${allFresh ? 'Các snapshot verified hiện còn trong cửa sổ current intelligence.' : 'Dataset AGING vẫn dùng được nhưng đang tiến gần ngưỡng stale.'}`;
        }
      }
      const side = document.getElementById('snapshotFreshnessSidebar');
      if(side) side.textContent = anyStale ? 'STALE BLOCKED' : anyUnknown ? 'UNKNOWN' : allFresh ? 'FRESH' : 'AGING';

      // Stale datasets must not look like a current-state panel even if another
      // frontend renderer writes after this script starts.
      observeStale('macroOverview', 'Macro Pulse', d.macro);
      observeStale('regionalOverview', 'Regional Radar', d.regional);
      observeStale('realityOverview', 'Reality Check / Counter-signals', d.contradiction);
    })
    .catch(() => {
      ensureSidebarMetric();
      const banner = ensureBanner();
      if(banner) banner.innerHTML = '<strong>Freshness state unavailable.</strong> Không nên coi snapshot verified là current cho tới khi pipeline xác nhận lại tuổi dữ liệu.';
      const side = document.getElementById('snapshotFreshnessSidebar');
      if(side) side.textContent = 'UNKNOWN';
    });
})();
