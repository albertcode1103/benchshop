(function () {
  const navigation = window.performance?.getEntriesByType?.("navigation")?.[0];
  if (navigation?.type !== "reload") return;

  const supportsScrollRestoration = "scrollRestoration" in window.history;
  const previousScrollRestoration = supportsScrollRestoration ? window.history.scrollRestoration : null;
  if (supportsScrollRestoration) window.history.scrollRestoration = "manual";

  const scrollToTop = () => window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  window.botenResetReloadScroll = scrollToTop;
  scrollToTop();
  window.addEventListener("pageshow", () => requestAnimationFrame(scrollToTop), { once: true });
  window.addEventListener("load", () => requestAnimationFrame(scrollToTop), { once: true });
  window.addEventListener("pagehide", () => {
    if (supportsScrollRestoration) window.history.scrollRestoration = previousScrollRestoration;
    delete window.botenResetReloadScroll;
  }, { once: true });
})();
