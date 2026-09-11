(function () {
  const supportsScrollRestoration = "scrollRestoration" in window.history;
  const previousScrollRestoration = supportsScrollRestoration ? window.history.scrollRestoration : null;
  if (supportsScrollRestoration) window.history.scrollRestoration = "manual";

  // Home entries (including history/BFCache returns) start at the top, while
  // the saved device/configuration/cart state is left untouched.
  const scrollToTop = () => window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  window.botenResetReloadScroll = scrollToTop;
  scrollToTop();
  window.addEventListener("pageshow", () => {
    if (supportsScrollRestoration) window.history.scrollRestoration = "manual";
    requestAnimationFrame(scrollToTop);
  });
  window.addEventListener("load", () => requestAnimationFrame(scrollToTop), { once: true });
  window.addEventListener("pagehide", () => {
    if (supportsScrollRestoration) window.history.scrollRestoration = previousScrollRestoration;
  });
})();
