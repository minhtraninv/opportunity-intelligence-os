(() => {
  const apply = (meta) => {
    const version = meta?.system_version || '—';
    const status = meta?.status_label || 'SYSTEM ONLINE';
    const header = document.getElementById('dataStatus');
    if (header) header.textContent = `V${version} · ${status}`;

    const footer = document.querySelector('footer span:first-child');
    if (footer) footer.textContent = `Opportunity Intelligence OS · V${version}`;
  };

  fetch('data/system_meta.json', {cache: 'no-store'})
    .then(r => r.ok ? r.json() : null)
    .then(meta => {
      if (!meta) return;
      apply(meta);

      const target = document.getElementById('dataStatus');
      if (!target) return;
      const observer = new MutationObserver(() => apply(meta));
      observer.observe(target, {childList: true, characterData: true, subtree: true});
      setTimeout(() => observer.disconnect(), 5000);
    })
    .catch(() => {});
})();
