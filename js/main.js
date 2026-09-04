async function initApp() {
  try {
    await loadCatalogFromApi();
  } catch (error) {
    const isEnglish = localStorage.getItem("boten-language") === "en";
    const deviceSelect = document.getElementById("device-select");
    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");
    const pageDesc = document.getElementById("page-desc");

    if (deviceSelect) {
      deviceSelect.innerHTML = `<option>${isEnglish ? "Catalog unavailable" : "设备目录加载失败"}</option>`;
      deviceSelect.disabled = true;
    }
    if (pageTitle) pageTitle.textContent = isEnglish ? "Unable to load catalog" : "无法加载设备目录";
    if (pageSubtitle) pageSubtitle.textContent = isEnglish ? "Please check the API service" : "请检查 API 服务";
    if (pageDesc) {
      pageDesc.textContent = isEnglish
        ? "Start the API service on port 8001, then refresh this page."
        : "请确认 8001 端口的 API 服务已启动，然后刷新页面。";
    }
    return;
  }
  initializeState();
  bindRenderer(state);
  initPricePreview();
  await initAuth();
  if (typeof initCatalogMarketplace === "function") initCatalogMarketplace();
  initCart();
  initReset();
  if (typeof window.botenResetReloadScroll === "function") {
    requestAnimationFrame(window.botenResetReloadScroll);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
