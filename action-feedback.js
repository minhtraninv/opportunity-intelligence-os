(() => {
  const esc = (v) => String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');

  let previousScores = null;
  let previousOrder = null;
  let ready = false;

  function currentRows(){
    try {
      if(typeof rankedOpps !== 'function') return [];
      return rankedOpps();
    } catch { return []; }
  }

  function currentFactors(opp){
    try {
      return {
        capital: typeof capitalFit === 'function' ? capitalFit(opp, state.capital) : null,
        time: typeof timeFit === 'function' ? timeFit(opp) : null,
        geo: typeof geoFit === 'function' ? geoFit(opp) : null,
      };
    } catch { return {capital:null,time:null,geo:null}; }
  }

  function scoreMap(rows){
    return Object.fromEntries(rows.map(x => [x.id, Number(x.personalized_score || 0)]));
  }

  function orderMap(rows){
    return Object.fromEntries(rows.map((x,i) => [x.id, i]));
  }

  function impactText(rows, compare){
    if(!compare || !previousScores || !previousOrder) return 'Thay đổi lựa chọn để xem mức ảnh hưởng lên Small Bets.';
    const nextScores = scoreMap(rows);
    const nextOrder = orderMap(rows);
    let changedScore = 0;
    let moved = 0;
    let biggest = null;
    rows.forEach(x => {
      if(previousScores[x.id] == null) return;
      const delta = nextScores[x.id] - previousScores[x.id];
      if(delta !== 0) changedScore += 1;
      if(previousOrder[x.id] !== nextOrder[x.id]) moved += 1;
      if(!biggest || Math.abs(delta) > Math.abs(biggest.delta)) biggest = {title:x.title, delta};
    });
    if(changedScore === 0 && moved === 0) return 'Lựa chọn vừa rồi không tạo khác biệt với dataset Small Bets hiện tại.';
    const bits = [`${changedScore} bet đổi điểm`, `${moved} bet đổi thứ tự`];
    if(biggest && biggest.delta !== 0) bits.push(`biến động lớn nhất ${biggest.delta > 0 ? '+' : ''}${biggest.delta}: ${biggest.title}`);
    return bits.join(' · ');
  }

  function geoExplanation(rows){
    let pref = 'all';
    try { pref = state.geo; } catch {}
    if(pref === 'all') return 'Địa lý đang không giới hạn.';
    const national = rows.filter(x => x.geo === 'national').length;
    if(national) return `${national}/${rows.length} bet hiện là Toàn quốc/online nên gần như không bị phạt theo vùng.`;
    return 'Địa lý đang tác động trực tiếp lên toàn bộ shortlist hiện tại.';
  }

  function render(compare=false){
    const box = document.getElementById('actionImpact');
    if(!box) return;
    const rows = currentRows();
    if(!rows.length){
      box.innerHTML = '<div class="muted small">Đang chờ Small Bet dataset…</div>';
      return;
    }

    const top = rows[0];
    const factors = currentFactors(top);
    const strong = rows.filter(x => Number(x.personalized_score || 0) >= 75).length;
    const constrained = rows.filter(x => String(x.action_fit_note || '').includes('vượt') || String(x.action_fit_note || '').includes('chậm') || String(x.action_fit_note || '').includes('ngoài vùng')).length;
    const impact = impactText(rows, compare);

    box.innerHTML = `
      <div class="action-impact-kicker">TÁC ĐỘNG HIỆN TẠI</div>
      <div class="action-impact-top"><strong>${esc(top.title)}</strong><span>${esc(top.personalized_score)}/100</span></div>
      <div class="action-impact-factors">
        <span>Vốn ${factors.capital ?? '—'}</span>
        <span>Time ${factors.time ?? '—'}</span>
        <span>Geo ${factors.geo ?? '—'}</span>
      </div>
      <div class="action-impact-line"><strong>${strong}</strong> bet fit cao · <strong>${constrained}</strong> bet đang bị constraint</div>
      <div class="action-impact-line">${esc(impact)}</div>
      <div class="action-impact-line muted">${esc(geoExplanation(rows))}</div>
      <button id="openSmallBetsFromAction" class="btn secondary action-impact-button">Mở shortlist Small Bets</button>
    `;

    document.getElementById('openSmallBetsFromAction')?.addEventListener('click', () => {
      try { switchTab('opportunities'); } catch {}
    });

    previousScores = scoreMap(rows);
    previousOrder = orderMap(rows);
    ready = true;
  }

  function waitForRows(attempt=0){
    const rows = currentRows();
    if(rows.length){ render(false); return; }
    if(attempt < 30) setTimeout(() => waitForRows(attempt + 1), 250);
  }

  ['capitalFilter','cashFilter','geoFilter'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => {
      setTimeout(() => render(ready), 0);
    });
  });

  waitForRows();
})();
