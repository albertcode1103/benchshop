(function () {
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  const languageKey = 'boten-language-scroll';
  let languagePosition = null;
  try {
    languagePosition = JSON.parse(sessionStorage.getItem(languageKey) || 'null');
    sessionStorage.removeItem(languageKey);
  } catch (_) {}
  const back = performance.getEntriesByType('navigation')[0]?.type === 'back_forward';
  const target = languagePosition || (back ? history.state?.botenScroll : null);
  let cancelled = false, started = false, observer = null, timer = null;
  function stop() { cancelled = true; observer?.disconnect(); clearTimeout(timer); }
  window.botenCancelScrollRestore = stop;
  ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach(type =>
    window.addEventListener(type, stop, { passive: true, once: true }));
  function capture() {
    const sections = [...document.querySelectorAll('.spec-section[id], #config-section, #catalog-marketplace')]
      .filter(el => el.getClientRects().length && el.getBoundingClientRect().top <= innerHeight / 2);
    const anchor = sections[sections.length - 1];
    return { y: scrollY, view: document.body.dataset.selectionView, model: document.getElementById('device-select')?.value,
      anchor: anchor?.id || null, offset: anchor?.getBoundingClientRect().top,
      overview: !!document.querySelector('.device-overview')?.open };
  }
  window.botenRememberLanguageScroll = () => {
    try { sessionStorage.setItem(languageKey, JSON.stringify(capture())); } catch (_) {}
  };
  function position() {
    if (cancelled) return;
    const sameModel = !target?.model || target.model === document.getElementById('device-select')?.value;
    const anchor = languagePosition && sameModel && target.anchor && document.getElementById(target.anchor);
    const y = !sameModel ? 0 : anchor && anchor.getClientRects().length
      ? scrollY + anchor.getBoundingClientRect().top - target.offset : target?.y || 0;
    window.scrollTo({ top: Math.max(0, y), left: 0, behavior: 'instant' });
  }
  window.botenResetReloadScroll = () => {
    if (started || cancelled) return;
    started = true;
    if (target) {
      const overview = document.querySelector('.device-overview');
      if (overview) overview.open = target.overview;
    }
    requestAnimationFrame(position);
    // Allow asynchronous image layout to settle, but never fight user input.
    if (target) {
      observer = new ResizeObserver(position); observer.observe(document.body);
      timer = setTimeout(() => observer.disconnect(), 3000);
    }
  };
  window.addEventListener('pagehide', () => {
    try { history.replaceState({ ...history.state, botenScroll: capture() }, ''); } catch (_) {}
    observer?.disconnect(); clearTimeout(timer);
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) stop(); // BFCache already retains the rendered position.
  });
})();
