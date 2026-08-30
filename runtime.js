(() => {
  'use strict';

  const nativeFetch = window.fetch.bind(window);
  const responseCache = new Map();
  const inflight = new Map();
  const CACHE_TTL_MS = 60_000;
  const META_CHECK_MS = 5 * 60_000;
  const TAB_KEY = 'oi.runtime.activeTab';

  const isDataRequest = (input, init) => {
    if((init?.method || 'GET').toUpperCase() !== 'GET') return false;
    try {
      const raw = typeof input === 'string' ? input : input?.url;
      if(!raw) return false;
      const url = new URL(raw, location.href);
      return url.origin === location.origin && /\/data\/[^/?]+\.json$/.test(url.pathname);
    } catch {
      return false;
    }
  };

  const dataKey = (input) => {
    const raw = typeof input === 'string' ? input : input?.url;
    const url = new URL(raw, location.href);
    url.searchParams.delete('_oi_ts');
    return url.href;
  };

  /* Same JSON, one network request per short session window. */
  window.fetch = function oiFetch(input, init = {}) {
    if(!isDataRequest(input, init)) return nativeFetch(input, init);

    const key = dataKey(input);
    const now = Date.now();
    const cached = responseCache.get(key);
    if(cached && now - cached.at < CACHE_TTL_MS){
      return Promise.resolve(cached.response.clone());
    }
    if(inflight.has(key)){
      return inflight.get(key).then(response => response.clone());
    }

    const request = nativeFetch(input, {...init, cache:'no-cache'})
      .then(response => {
        if(response.ok) responseCache.set(key, {at:Date.now(), response:response.clone()});
        return response;
      })
      .finally(() => inflight.delete(key));
    inflight.set(key, request);
    return request.then(response => response.clone());
  };

  const loadedScripts = new Map();
  function loadScript(src){
    if(loadedScripts.has(src)) return loadedScripts.get(src);
    const promise = new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-oi-lazy="${src}"]`);
      if(existing){
        if(existing.dataset.loaded === '1') resolve();
        else existing.addEventListener('load', resolve, {once:true});
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.dataset.oiLazy = src;
      script.addEventListener('load', () => { script.dataset.loaded = '1'; resolve(); }, {once:true});
      script.addEventListener('error', () => reject(new Error(`Không tải được ${src}`)), {once:true});
      document.body.appendChild(script);
    });
    loadedScripts.set(src, promise);
    return promise;
  }

  let reportsLoaded = false;
  let advancedLoaded = false;

  async function loadReports(){
    if(reportsLoaded) return;
    reportsLoaded = true;
    try {
      await loadScript('reports.js');
    } catch(err){
      reportsLoaded = false;
      console.error(err);
    }
  }

  async function loadAdvanced(){
    if(advancedLoaded) return;
    advancedLoaded = true;
    try {
      await loadScript('action.js');
      await loadScript('relationship.js');
      await loadScript('counterparty.js');
      await loadScript('execution.js');
    } catch(err){
      advancedLoaded = false;
      console.error(err);
    }
  }

  function activeTab(){
    return document.querySelector('.tab.active')?.dataset.tab || 'overview';
  }

  function rememberTab(){
    try { sessionStorage.setItem(TAB_KEY, activeTab()); } catch {}
  }

  function restoreTab(){
    let id = null;
    try { id = sessionStorage.getItem(TAB_KEY); sessionStorage.removeItem(TAB_KEY); } catch {}
    if(!id || id === 'overview') return;
    requestAnimationFrame(() => document.querySelector(`.tab[data-tab="${id}"]`)?.click());
  }

  document.addEventListener('click', event => {
    const tab = event.target.closest('.tab[data-tab]');
    if(!tab) return;
    const id = tab.dataset.tab;
    if(id === 'reports') loadReports();
    if(id === 'buyers') loadAdvanced();
  });

  function setFreshnessMessage(text){
    const target = document.getElementById('updatedAt');
    if(target) target.textContent = text;
  }

  async function readMeta(){
    try {
      const response = await nativeFetch(`data/system_meta.json?_oi_ts=${Date.now()}`, {cache:'no-store'});
      if(!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  }

  let currentMetaStamp = null;
  async function initializeFreshness(){
    const meta = await readMeta();
    currentMetaStamp = meta?.latest_component_update || meta?.generated_at || null;
  }

  async function checkForUpdate(){
    if(document.hidden) return;
    const meta = await readMeta();
    const next = meta?.latest_component_update || meta?.generated_at || null;
    if(!next) return;
    if(!currentMetaStamp){ currentMetaStamp = next; return; }
    if(next === currentMetaStamp) return;

    currentMetaStamp = next;
    responseCache.clear();
    rememberTab();
    setFreshnessMessage('Có dữ liệu mới · đang cập nhật…');
    window.setTimeout(() => location.reload(), 350);
  }

  window.OIRuntime = {
    loadReports,
    loadAdvanced,
    clearDataCache: () => responseCache.clear(),
    checkForUpdate,
  };

  restoreTab();
  initializeFreshness();
  window.setInterval(checkForUpdate, META_CHECK_MS);
  document.addEventListener('visibilitychange', () => {
    if(!document.hidden) checkForUpdate();
  });
})();