/* User-site only. Loaded before styles to avoid a light flash; no API writes. */
(() => {
  const key = 'boten-theme';
  const system = matchMedia('(prefers-color-scheme: dark)');
  let preference = null;
  try { preference = localStorage.getItem(key); } catch (_) {}
  if (!['dark', 'light'].includes(preference)) preference = null;
  function render() {
    const dark = preference ? preference === 'dark' : system.matches;
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#14181e' : '#ffffff');
    const button = document.getElementById('account-theme-toggle');
    if (button) {
      let english = document.documentElement.lang.startsWith('en');
      try { english = localStorage.getItem('boten-language') === 'en'; } catch (_) {}
      button.querySelector('.theme-label').textContent = english ? 'Dark Mode' : '深色模式';
      button.setAttribute('aria-checked', String(dark));
    }
  }
  render();
  system.addEventListener('change', () => { if (!preference) render(); });
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = ['dark','light'].includes(event.newValue) ? event.newValue : null;
    render();
  });
  document.addEventListener('DOMContentLoaded', () => {
    render();
    document.getElementById('account-theme-toggle')?.addEventListener('click', () => {
      preference = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, preference); } catch (_) {}
      render();
    });
  });
})();
